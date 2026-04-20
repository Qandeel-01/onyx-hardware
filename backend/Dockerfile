# ── Stage 1: system deps + Python deps ──────────────────────────────
FROM python:3.11-slim AS base

# System dependencies for asyncpg, curl healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: development (hot-reload, source mounted as volume) ──────
FROM base AS dev

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Stage 3: production (gunicorn, minimal) ─────────────────────────
FROM base AS prod

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY . .

EXPOSE 8000

CMD ["gunicorn", "--workers=4", "--worker-class=uvicorn.workers.UvicornWorker", \
     "--bind=0.0.0.0:8000", "--timeout=120", "app.main:app"]
