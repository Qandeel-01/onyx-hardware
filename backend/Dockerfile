# ── Stage 1: system deps + Python deps ──────────────────────────────
FROM python:3.11-slim AS base

# OpenCV headless needs these system libraries.
# ffmpeg is required for cv_worker video probing.
# libpq-dev is needed by asyncpg to compile against libpq.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libopencv-dev \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        ffmpeg \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --default-timeout=1000 -e "."

# ── Stage 2: development (hot-reload, source mounted as volume) ──────
FROM base AS dev

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# ── Stage 3: production (gunicorn, minimal) ─────────────────────────
FROM base AS prod

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY . .

EXPOSE 8000

CMD ["gunicorn", "--workers=4", "--worker-class=uvicorn.workers.UvicornWorker", \
     "--bind=0.0.0.0:8000", "--timeout=120", "app.main:app"]
