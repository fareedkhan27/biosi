# Local development only — Railway uses Nixpacks (no root Dockerfile).
# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN addgroup --system biosi && adduser --system --ingroup biosi biosi

WORKDIR /app

COPY --from=builder /install /usr/local

COPY start.sh ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN find /app -name '*.pyc' -delete \
 && find /app -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
RUN chmod 755 /app/start.sh

USER biosi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://localhost:{os.getenv('PORT', '8000')}/api/v1/health\")"

CMD ["sh", "./start.sh"]
