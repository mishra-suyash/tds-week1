# Stats Service

FastAPI service for `GET /stats?values=1,2,3`.

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
