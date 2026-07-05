# Stats Service

FastAPI service for `GET /stats?values=1,2,3`.

It also exposes `POST /verify` for RS256 JWT verification.

It also exposes `GET /effective-config` for layered configuration merging.

It also exposes `POST /analytics` for API-key-protected event aggregation.

It also exposes `GET /work`, `GET /metrics`, `GET /healthz`, and `GET /logs/tail` for live instrumentation checks.

## Local setup

```bash
cd stats_service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/stats?values=1,2,3
```

Verify a JWT:

```bash
curl -X POST http://127.0.0.1:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"<JWT string>"}'
```

Submit the deployed endpoint with the full path:

```text
https://your-app.example.com/verify
```

Check effective config:

```bash
curl "http://127.0.0.1:8000/effective-config?set=port=9000&set=debug=true"
```

The deployed service must have this OS-level environment variable:

```text
APP_PORT=8392
```

Submit the deployed endpoint with the full path:

```text
https://your-app.example.com/effective-config
```

Aggregate analytics:

```bash
curl -X POST http://127.0.0.1:8000/analytics \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_rm8smrs98bj5uzhjirm0todf" \
  -d '{"events":[{"user":"alice","amount":42.5,"ts":1700000000}]}'
```

Submit the deployed endpoint with the full path:

```text
https://your-app.example.com/analytics
```

Instrumentation endpoints:

```text
https://your-app.example.com/work?n=3
https://your-app.example.com/metrics
https://your-app.example.com/healthz
https://your-app.example.com/logs/tail?limit=10
```

Submit the deployed service base URL:

```text
https://your-app.example.com
```

## CORS

Only this origin is allowed:

```text
https://dash-2exq4z.example.com
```

## Deploy

This folder includes `requirements.txt`, `Procfile`, and `render.yaml`, so it can be deployed on Render as a Python web service. Use:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

as the start command if your host asks for one.
# tds-stats-service
# tds-week1
<<<<<<< HEAD
# tds-week1
=======
>>>>>>> 8f31fe4 (first commit)
# tds-week1
# tds-week1
# tds-week1
# tds-week1
# tds-week1
# tds-week1
