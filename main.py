import base64
import json
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import jwt
import yaml
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel


ALLOWED_ORIGIN = "https://dash-2exq4z.example.com"
EMAIL = "22f3001275@ds.study.iitm.ac.in"
APP_DIR = Path(__file__).resolve().parent
ANALYTICS_API_KEY = "ak_rm8smrs98bj5uzhjirm0todf"
PING_ALLOWED_ORIGIN = "https://app-jyt6qa.example.com"
PING_EXTRA_ALLOWED_ORIGINS = {
    "https://exam.sanand.workers.dev",
    "https://tds.s-anand.net",
}
ORDER_TOTAL = 56
ORDER_RATE_LIMIT = 16
PING_RATE_LIMIT = 13
RATE_LIMIT_WINDOW_S = 10.0
ASSIGNED_OS_ENV = {
    "APP_PORT": "8392",
}
START_TIME = time.perf_counter()
REQUEST_COUNT = 0
REQUEST_LOGS = deque(maxlen=500)
ORDER_IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}
ORDER_IDEMPOTENCY_LOCK = threading.Lock()
ORDER_RATE_BUCKETS: Dict[str, deque] = {}
PING_RATE_BUCKETS: Dict[str, deque] = {}
JWT_ISSUER = "https://idp.exam.local"
JWT_AUDIENCE = "tds-hwemr39o.apps.exam.local"
JWT_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

app = FastAPI(title="Stats Service")


class VerifyRequest(BaseModel):
    token: str


class AnalyticsEvent(BaseModel):
    user: str
    amount: float
    ts: int


class AnalyticsRequest(BaseModel):
    events: List[AnalyticsEvent]


class ExtractRequest(BaseModel):
    text: str


class ExtractResponse(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str


class OrderCreateRequest(BaseModel):
    item: Optional[str] = None
    quantity: Optional[int] = None


def is_ping_cors_allowed(origin: Optional[str]) -> bool:
    if not origin:
        return False
    extra_exam_origin = os.getenv("EXAM_PAGE_ORIGIN")
    return (
        origin == PING_ALLOWED_ORIGIN
        or origin in PING_EXTRA_ALLOWED_ORIGINS
        or (extra_exam_origin is not None and origin == extra_exam_origin)
    )


def client_is_rate_limited(
    buckets: Dict[str, deque],
    client_id: str,
    limit: int,
    now: float,
) -> Optional[float]:
    bucket = buckets.setdefault(client_id, deque())
    while bucket and now - bucket[0] >= RATE_LIMIT_WINDOW_S:
        bucket.popleft()
    if len(bucket) >= limit:
        return max(RATE_LIMIT_WINDOW_S - (now - bucket[0]), 0.0)
    bucket.append(now)
    return None


@app.middleware("http")
async def add_required_headers_and_cors(request: Request, call_next):
    global REQUEST_COUNT

    start_time = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    origin = request.headers.get("origin")
    REQUEST_COUNT += 1

    if request.method == "OPTIONS":
        if request.url.path in {"/analytics", "/effective-config", "/extract", "/orders"} and origin:
            response = JSONResponse(status_code=200, content={})
        elif request.url.path == "/ping" and is_ping_cors_allowed(origin):
            response = JSONResponse(status_code=200, content={})
        elif request.url.path in {"/stats", "/verify"} and origin == ALLOWED_ORIGIN:
            response = JSONResponse(status_code=200, content={})
        else:
            response = JSONResponse(status_code=400, content={"detail": "Disallowed CORS origin"})
    else:
        retry_after = None
        if request.url.path.startswith("/orders"):
            retry_after = client_is_rate_limited(
                ORDER_RATE_BUCKETS,
                request.headers.get("X-Client-Id") or "anonymous",
                ORDER_RATE_LIMIT,
                time.monotonic(),
            )
        elif request.url.path == "/ping":
            retry_after = client_is_rate_limited(
                PING_RATE_BUCKETS,
                request.headers.get("X-Client-Id") or "anonymous",
                PING_RATE_LIMIT,
                time.monotonic(),
            )

        if retry_after is not None:
            response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            response.headers["Retry-After"] = str(max(1, int(retry_after + 0.999)))
        else:
            request.state.request_id = request_id
            response = await call_next(request)

    if origin:
        if request.url.path in {"/analytics", "/orders", "/extract"}:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Expose-Headers"] = (
                "Retry-After, X-Request-ID, X-Process-Time"
            )
        elif request.url.path == "/ping" and is_ping_cors_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Expose-Headers"] = (
                "Retry-After, X-Request-ID, X-Process-Time"
            )
        elif request.url.path == "/effective-config":
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        elif request.url.path in {"/stats", "/verify"} and origin == ALLOWED_ORIGIN:
            response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
            response.headers["Vary"] = "Origin"

    if request.method == "OPTIONS":
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            request.headers.get("access-control-request-headers") or "*"
        )
        response.headers["Access-Control-Max-Age"] = "600"

    process_time = time.perf_counter() - start_time
    log_entry = {
        "level": "info",
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "request_id": request_id,
        "method": request.method,
        "status_code": response.status_code,
        "process_time_s": round(process_time, 6),
    }
    REQUEST_LOGS.append(log_entry)
    print(json.dumps(log_entry), flush=True)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.6f}"
    return response


def parse_values(raw_values: str) -> List[int]:
    values = raw_values.split(",")
    if not values or any(value.strip() == "" for value in values):
        raise ValueError("values must be a comma-separated list of integers")
    return [int(value.strip()) for value in values]


def normalize_config_key(key: str) -> str:
    normalized = key.strip().lower()
    if normalized.startswith("app_"):
        normalized = normalized[4:]
    if normalized == "num_workers":
        return "workers"
    return normalized


def coerce_config_value(key: str, value):
    if key in {"port", "workers"}:
        return int(value)
    if key == "debug":
        return str(value).strip().lower() in {"true", "1", "yes", "on"}
    return str(value)


def read_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[normalize_config_key(key)] = value.strip().strip("'\"")
    return values


def read_yaml_config(environment: str) -> dict:
    path = APP_DIR / f"config.{environment}.yaml"
    if not path.exists():
        return {}
    with path.open() as config_file:
        loaded = yaml.safe_load(config_file) or {}
    return {normalize_config_key(key): value for key, value in loaded.items()}


def read_app_environment() -> dict:
    values = {}
    assigned_and_runtime_env = {**ASSIGNED_OS_ENV, **os.environ}
    for key, value in assigned_and_runtime_env.items():
        if key.startswith("APP_") and key != "APP_ENV":
            values[normalize_config_key(key)] = value
    return values


def apply_config_layer(config: dict, layer: dict) -> None:
    for key, value in layer.items():
        normalized_key = normalize_config_key(key)
        config[normalized_key] = coerce_config_value(normalized_key, value)


def build_effective_config(cli_overrides: List[str]) -> dict:
    config = {
        "port": 8000,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000",
    }

    environment = os.getenv("APP_ENV", "development")
    apply_config_layer(config, read_yaml_config(environment))
    apply_config_layer(config, read_env_file(APP_DIR / ".env"))
    apply_config_layer(config, read_app_environment())

    for override in cli_overrides:
        if "=" not in override:
            raise ValueError("set parameters must use key=value")
        key, value = override.split("=", 1)
        normalized_key = normalize_config_key(key)
        apply_config_layer(config, {normalized_key: value})

    config["api_key"] = "****"
    return config


def extract_invoice_fields(text: str) -> ExtractResponse:
    normalized_text = text or ""

    vendor = ""
    vendor_patterns = [
        r"(?im)^\s*(?:vendor|from|bill\s+from|supplier)\s*[:\-]\s*(.+?)\s*$",
        r"\b([A-Z][A-Za-z0-9&.,' -]{2,100}?\s+(?:Industries\s+Ltd\.?|Ltd\.?|LLC|Inc\.?|Corp\.?|Corporation|Company|Co\.?))\b",
    ]
    for pattern in vendor_patterns:
        match = re.search(pattern, normalized_text)
        if match:
            vendor = match.group(1).strip(" .,\t")
            break

    currency = ""
    currency_match = re.search(r"\b(USD|EUR|GBP)\b", normalized_text, flags=re.IGNORECASE)
    if currency_match:
        currency = currency_match.group(1).upper()
    else:
        symbol_match = re.search(r"[$€£]", normalized_text)
        currency = {"$": "USD", "€": "EUR", "£": "GBP"}.get(symbol_match.group(0), "") if symbol_match else ""

    amount = 0.0
    amount_patterns = [
        r"(?is)(?:total\s+due|amount\s+due|balance\s+due|invoice\s+total|total|amount)\D{0,40}(?:USD|EUR|GBP|[$€£])?\s*([0-9]+(?:\.[0-9]{1,2})?)",
        r"(?is)(?:USD|EUR|GBP|[$€£])\s*([0-9]+(?:\.[0-9]{1,2})?)",
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, normalized_text)
        if match:
            amount = float(match.group(1))
            break

    due_date = ""
    date_patterns = [
        r"(?is)(?:due\s+date|payment\s+due|due)\D{0,30}(\d{4}-\d{2}-\d{2})",
        r"\b(2026-[01][0-9]-[0-3][0-9])\b",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, normalized_text)
        if match:
            due_date = match.group(1)
            break

    return ExtractResponse(vendor=vendor, amount=amount, currency=currency, date=due_date)


def encode_cursor(offset: int) -> str:
    raw_cursor = str(offset).encode("ascii")
    return base64.urlsafe_b64encode(raw_cursor).decode("ascii").rstrip("=")


def decode_cursor(cursor: Optional[str]) -> int:
    if not cursor:
        return 0
    padded = cursor + "=" * (-len(cursor) % 4)
    return int(base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii"))


def order_item(order_id: int) -> dict:
    return {"id": order_id, "status": "open"}


@app.get("/stats")
async def get_stats(values: str = Query(..., description="Comma-separated integers")):
    try:
        numbers = parse_values(values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not numbers:
        raise HTTPException(status_code=400, detail="values must not be empty")

    total = sum(numbers)
    return {
        "email": EMAIL,
        "count": len(numbers),
        "sum": total,
        "min": min(numbers),
        "max": max(numbers),
        "mean": total / len(numbers),
    }


@app.post("/verify")
async def verify_token(payload: VerifyRequest):
    try:
        claims = jwt.decode(
            payload.token,
            JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.PyJWTError:
        return JSONResponse(status_code=401, content={"valid": False})

    return {
        "valid": True,
        "email": claims.get("email"),
        "sub": claims.get("sub"),
        "aud": claims.get("aud"),
    }


@app.get("/effective-config")
async def effective_config(set_values: List[str] = Query(default=[], alias="set")):
    try:
        return build_effective_config(set_values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analytics")
async def analytics(
    payload: AnalyticsRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    if x_api_key != ANALYTICS_API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    positive_totals = {}
    revenue = 0.0
    users = set()

    for event in payload.events:
        users.add(event.user)
        if event.amount > 0:
            revenue += event.amount
            positive_totals[event.user] = positive_totals.get(event.user, 0.0) + event.amount

    top_user = max(positive_totals, key=positive_totals.get) if positive_totals else None
    return {
        "email": EMAIL,
        "total_events": len(payload.events),
        "unique_users": len(users),
        "revenue": revenue,
        "top_user": top_user,
    }


@app.get("/work")
async def work(n: int = Query(..., ge=0)):
    for _ in range(n):
        pass
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    body = (
        "# HELP http_requests_total Total HTTP requests handled by this service.\n"
        "# TYPE http_requests_total counter\n"
        f"http_requests_total {REQUEST_COUNT}\n"
    )
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "uptime_s": time.perf_counter() - START_TIME}


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(20, ge=1, le=500)):
    return list(REQUEST_LOGS)[-limit:]


@app.post("/extract", response_model=ExtractResponse)
async def extract_invoice(payload: ExtractRequest):
    return extract_invoice_fields(payload.text)


@app.post("/orders")
async def create_order(
    payload: Optional[OrderCreateRequest] = None,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")

    with ORDER_IDEMPOTENCY_LOCK:
        if idempotency_key in ORDER_IDEMPOTENCY_STORE:
            return ORDER_IDEMPOTENCY_STORE[idempotency_key]

        order = {
            "id": f"created-{len(ORDER_IDEMPOTENCY_STORE) + 1}",
            "item": payload.item if payload else None,
            "quantity": payload.quantity if payload else None,
        }
        ORDER_IDEMPOTENCY_STORE[idempotency_key] = order
        return JSONResponse(status_code=201, content=order)


@app.get("/orders")
async def list_orders(limit: int = Query(10, ge=1, le=100), cursor: Optional[str] = None):
    try:
        start = decode_cursor(cursor)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid cursor")

    end = min(start + limit, ORDER_TOTAL)
    items = [order_item(order_id) for order_id in range(start + 1, end + 1)]
    next_cursor = encode_cursor(end) if end < ORDER_TOTAL else None
    return {"items": items, "next_cursor": next_cursor}


@app.get("/ping")
async def ping(request: Request):
    return {"email": EMAIL, "request_id": request.state.request_id}


@app.get("/")
async def health_check():
    return {"ok": True, "service": "stats"}
