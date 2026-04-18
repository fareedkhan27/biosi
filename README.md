# Biosi — Biosimilar Competitive Intelligence Platform

[![CI](https://github.com/fareedkhan27/biosi/actions/workflows/ci.yml/badge.svg)](https://github.com/fareedkhan27/biosi/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)]()

> Real-time competitive intelligence for biosimilar pipeline tracking — built for enterprise scale.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Local Development Setup](#local-development-setup)
4. [Database Migrations](#database-migrations)
5. [Seed Reference Data](#seed-reference-data)
6. [Running the API](#running-the-api)
7. [Docker](#docker)
8. [Testing](#testing)
9. [Code Quality](#code-quality)
10. [Environment Variables Reference](#environment-variables-reference)
11. [Branching Strategy](#branching-strategy)
12. [Contributing](#contributing)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                          │
│  app/api/v1/         ← HTTP layer (routes, schemas)         │
│  app/core/           ← Config, logging, exceptions          │
│  app/models/         ← SQLAlchemy ORM models                │
│  app/schemas/        ← Pydantic request / response models   │
│  app/db/             ← Session factory, seed scripts        │
├─────────────────────────────────────────────────────────────┤
│  Alembic             ← Schema migrations (psycopg / direct) │
├─────────────────────────────────────────────────────────────┤
│  Neon PostgreSQL     ← Pooled (asyncpg) + Direct (psycopg)  │
└─────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- Async-first: `asyncpg` for runtime, `psycopg` only for migrations.
- 12-factor config: all settings via env vars, validated by `pydantic-settings`.
- Typed end-to-end: strict `mypy`, Pydantic v2 response models on every route.
- Single virtual environment at `Biosi/.venv` — no nested envs.

---

## Project Structure

```
Biosi/
├── .github/
│   ├── workflows/ci.yml          # Lint → typecheck → test pipeline
│   └── PULL_REQUEST_TEMPLATE.md
├── app/
│   ├── api/
│   │   ├── deps.py               # Shared FastAPI dependencies (DB session, etc.)
│   │   └── v1/
│   │       ├── router.py         # Aggregate router for all v1 endpoints
│   │       └── health.py
│   ├── core/
│   │   ├── config.py             # Pydantic Settings (all env vars here)
│   │   ├── db.py                 # Re-exports session helpers
│   │   ├── exceptions.py         # Domain exception hierarchy
│   │   └── logging.py            # Structured JSON logging
│   ├── db/
│   │   ├── session.py            # Async engine + session factory
│   │   ├── url.py                # DB URL normalization (asyncpg / psycopg)
│   │   ├── seed.py               # Entry point: python -m app.db.seed
│   │   ├── seed_data.py          # Static seed payloads
│   │   └── seeds.py              # Upsert logic
│   ├── models/
│   │   ├── base.py               # DeclarativeBase with naming convention
│   │   ├── mixins.py             # UUIDPrimaryKeyMixin, TimestampMixin
│   │   ├── competitor.py
│   │   ├── source.py
│   │   ├── source_document.py
│   │   ├── event.py
│   │   ├── review.py
│   │   └── scoring_rule.py
│   ├── schemas/
│   │   └── health.py             # Pydantic response model for /health
│   └── main.py                   # App factory (lifespan, CORS, routers, handlers)
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   └── api/v1/test_health.py
├── .env.example                  # Copy to .env — never commit .env
├── .gitignore
├── .pre-commit-config.yaml
├── alembic.ini
├── docker-compose.yml
├── Dockerfile                    # Multi-stage, non-root user
├── pyproject.toml                # ruff, mypy, pytest config
├── requirements.txt              # Runtime deps
└── requirements-dev.txt          # Dev + CI deps
```

---

## Local Development Setup

### Prerequisites

- Python 3.12+
- Git

### 1. Clone & enter the project

```bash
git clone https://github.com/fareedkhan27/biosi.git
cd biosi
```

### 2. Create the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
# Runtime
pip install -r requirements.txt

# Development (adds ruff, mypy, pytest, pre-commit)
pip install -r requirements-dev.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in DATABASE_URL, DATABASE_URL_DIRECT, SECRET_KEY
```

### 5. Install pre-commit hooks

```bash
pre-commit install
```

---

## Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Create a new autogenerated migration
alembic revision --autogenerate -m "describe_your_change"

# Downgrade one step
alembic downgrade -1
```

> Alembic uses `DATABASE_URL_DIRECT` (psycopg / direct connection) — not the pooled URL.

---

## Seed Reference Data

```bash
python -m app.db.seed
```

Idempotent — safe to run multiple times. Seeds:
- **Sources**: ClinicalTrials.gov, EMA, FDA
- **Scoring rules**: trial phase change, approval/rejection, label update

---

## Running the API

```bash
# Development (hot reload)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Production-like
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

| Endpoint | Description |
|---|---|
| `GET /api/v1/health` | Liveness check |
| `GET /docs` | Swagger UI (dev/staging only) |
| `GET /redoc` | ReDoc (dev/staging only) |

---

## Docker

```bash
# Build & run
docker compose up --build

# Stop
docker compose down
```

For local hot-reload, create `docker-compose.override.yml`:

```yaml
services:
  web:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app:cached
```

---

## Testing

```bash
# Run all tests with coverage
pytest

# Run a specific test file
pytest tests/api/v1/test_health.py -v

# Coverage report only
pytest --cov=app --cov-report=html
```

---

## Code Quality

```bash
# Lint (auto-fix)
ruff check . --fix

# Format
ruff format .

# Type check
mypy app

# Run all pre-commit hooks manually
pre-commit run --all-files
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | No | `dev` | `dev` \| `staging` \| `production` \| `test` |
| `SECRET_KEY` | **Yes** | — | Min 32-char random string |
| `DATABASE_URL` | **Yes** | — | Pooled asyncpg URL for runtime |
| `DATABASE_URL_DIRECT` | **Yes** | — | Direct psycopg URL for migrations |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:8000` | Comma-separated allowed origins |
| `OPENROUTER_API_KEY` | No | — | OpenRouter key (Milestone 3+) |
| `OPENROUTER_MODEL_PRIMARY` | No | `anthropic/claude-3.7-sonnet` | Primary LLM model |
| `OPENROUTER_MODEL_FALLBACK` | No | `google/gemini-2.0-flash-001` | Fallback LLM model |
| `CLINICALTRIALS_BASE_URL` | No | `https://clinicaltrials.gov/api/query/studies` | ClinicalTrials API base |
| `N8N_WEBHOOK_BASE_URL` | No | — | n8n webhook base (Milestone 4+) |

---

## Branching Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code; protected, PR-only |
| `develop` | Integration branch for features |
| `feat/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `chore/<name>` | Tooling, dependencies, docs |

---

## Contributing

1. Branch from `develop`: `git checkout -b feat/your-feature develop`
2. Write code + tests (coverage ≥ 80%)
3. Run `pre-commit run --all-files` and ensure it passes
4. Open a PR against `develop` using the PR template
5. Squash-merge after review

> **Never commit** `.env`, `.venv/`, or any credentials.
