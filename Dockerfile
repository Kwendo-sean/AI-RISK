# Multi-arch: builds for linux/amd64 (server) and linux/arm64 (Raspberry Pi 4/5, 64-bit OS).
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl is only used by the container healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so application edits do not invalidate the layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run unprivileged. /data holds the SQLite file when Postgres is not used.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /data \
 && chown -R appuser:appuser /app /data
USER appuser

ENV DB_PATH=/data/willaijob.db \
    PORT=8000 \
    WEB_CONCURRENCY=4

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/v2/ready" || exit 1

# Uvicorn's own multi-worker mode: one supervisor, WEB_CONCURRENCY workers.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --no-access-log --proxy-headers --forwarded-allow-ips='*'"]
