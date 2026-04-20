# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12.9-slim AS builder

WORKDIR /build

COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12.9-slim AS runtime

# Non-root user for security
RUN addgroup --system biosi && adduser --system --ingroup biosi biosi

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source (no .env baked in)
# Cache-bust: forces fresh COPY app layer (fixes DISTINCT ON regression 2026-04-21)
RUN echo "cache-bust-2026-04-21-distinct-on-fix" > /dev/null
COPY start.sh ./
COPY app ./app
# Purge any stale bytecode shipped by accident
RUN find /app -name '*.pyc' -delete && find /app -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
COPY alembic ./alembic
COPY alembic.ini ./

RUN chmod 755 /app/start.sh

USER biosi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://localhost:{os.getenv('PORT', '8000')}/api/v1/health\")"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
