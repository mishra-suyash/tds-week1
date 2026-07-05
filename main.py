import time
from typing import List
from uuid import uuid4

import jwt
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


ALLOWED_ORIGIN = "https://dash-2exq4z.example.com"
EMAIL = "22f3001275@ds.study.iitm.ac.in"
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class VerifyRequest(BaseModel):
    token: str


@app.middleware("http")
async def add_required_headers(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Request-ID"] = str(uuid4())
    response.headers["X-Process-Time"] = f"{process_time:.6f}"
    return response


def parse_values(raw_values: str) -> List[int]:
    values = raw_values.split(",")
    if not values or any(value.strip() == "" for value in values):
        raise ValueError("values must be a comma-separated list of integers")
    return [int(value.strip()) for value in values]


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


@app.get("/")
async def health_check():
    return {"ok": True, "service": "stats"}
