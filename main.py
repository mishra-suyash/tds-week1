import time
from typing import List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware


ALLOWED_ORIGIN = "https://dash-2exq4z.example.com"
EMAIL = "iamsuyashbharat@gmail.com"

app = FastAPI(title="Stats Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


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


@app.get("/")
async def health_check():
    return {"ok": True, "service": "stats"}
