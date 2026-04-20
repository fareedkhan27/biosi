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
7. [Deployment on Railway](#deployment-on-railway)
8. [Docker](#docker)
9. [Testing](#testing)
10. [Milestone 6 Demo Flow (<5 Minutes)](#milestone-6-demo-flow-5-minutes)
11. [Workflow Automation](#workflow-automation)
12. [Code Quality](#code-quality)
13. [Environment Variables Reference](#environment-variables-reference)
14. [Branching Strategy](#branching-strategy)
15. [Contributing](#contributing)

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
├── docker/
│   └── Dockerfile                # Local Docker image definition
├── docker-compose.yml
├── pyproject.toml                # ruff, mypy, pytest config
├── requirements.txt              # Runtime deps
└── requirements-dev.txt          # Dev + CI deps
```

---

## Local Development Setup

### Prerequisites

- Python 3.12+
- Git
- PostgreSQL database (local Postgres or Neon)
- A configured `.env` with working `DATABASE_URL` and `DATABASE_URL_DIRECT`

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

> Note: For n8n integration, use the Railway production API URL (`https://biosi-production.up.railway.app`) directly. No tunnel setup is required.

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
# Seeds source metadata + scoring rules (idempotent)
python -m app.db.seed

# Seeds Milestone 6 demo competitors + events (idempotent)
python -m scripts.seeddemodata
```

Both commands are idempotent and safe to run multiple times.

Reference seed includes:
- **Sources**: ClinicalTrials.gov, EMA, FDA
- **Scoring rules**: trial phase change, approval/rejection, label update

Demo seed includes:
- **Amgen / ABP 206** (clinical development, Phase 3, Amber-style)
- **Henlius / HLX18** (regulatory IND-style, Amber-style)
- **India launch-style narrative** (Zydus)

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
| `POST /api/v1/jobs/ingest/clinicaltrials` | Run ClinicalTrials.gov API v2 ingestion |
| `POST /api/v1/jobs/ingest/press-release` | Extract and ingest a press-release event via OpenRouter |
| `GET /api/v1/dashboards/summary` | Dashboard totals by review status + traffic light |
| `GET /api/v1/dashboards/top-threats` | Highest-risk events first |
| `GET /api/v1/dashboards/recent-events` | Most recent events first |
| `GET /api/v1/dashboards/review-queue` | Pending analyst review queue |
| `GET /docs` | Swagger UI (dev/staging only) |
| `GET /redoc` | ReDoc (dev/staging only) |

---

## Deployment on Railway

Biosi is deployed on Railway using **Railpack** (the default Railway builder).

Production API URL: https://biosi-production.up.railway.app

### Service root directory

This GitHub repository already has the application at the repository root.

- In Railway, keep **Root Directory** empty / unset for this service.
- Run Railway deployments from this `Biosi` directory when using the CLI.

Railway deployment uses the service config in this repository and does not require a separate parent-folder wrapper.

### Start command

Railway is configured (via `railway.toml`) to run:

```sh
sh ./start.sh
```

`start.sh` starts the FastAPI app with Uvicorn and binds to Railway's `PORT` environment variable.
Make sure the script is executable before committing:

```bash
chmod +x start.sh
git add start.sh
git commit -m "chore: mark start.sh executable"
```

### Environment variables

Railway automatically injects `PORT`; the app binds to it via `${PORT:-8000}`.
All other secrets must be set in Railway **Variables** — never committed to Git:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_DIRECT` | Direct (non-pooled) PostgreSQL URL for Alembic |
| `SECRET_KEY` | Application secret key |
| `OPENROUTER_API_KEY` | OpenRouter LLM API key |
| `APP_ENV` | Set to `production` |

### Deploy a new version

```bash
railway up --detach
```

Run that command from the repository root, i.e. this `Biosi` directory.

### View logs

```bash
railway logs
```

### Update environment variables

```bash
railway variables set KEY="value"
```

---

## Docker

Docker is optional and intended for local development only. The local image definition lives at `docker/Dockerfile` so Railway can use Railpack without Dockerfile detection ambiguity.

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

# Optional: integration-only run
pytest tests/integration -v
```

---

## Milestone 6 Demo Flow (<5 Minutes)

This is the fastest demo path for API-only walkthroughs.

### 1) Start from project root and activate environment

```bash
cd /Users/fareedkhan/Dev/personal/Biosimilar/Biosi
source .venv/bin/activate
```

### 2) Apply migrations

```bash
alembic upgrade head
```

### 3) Seed reference + demo data

```bash
python -m app.db.seed
python -m scripts.seeddemodata
```

### 4) Start API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5) Validate health and open docs

```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 6) Demo API sequence (copy/paste)

```bash
# List events (shows seeded demo records)
curl -s "http://127.0.0.1:8000/api/v1/events" | jq

# Dashboard summary
curl -s "http://127.0.0.1:8000/api/v1/dashboards/summary" | jq

# Highest-risk events first
curl -s "http://127.0.0.1:8000/api/v1/dashboards/top-threats" | jq

# Latest events first
curl -s "http://127.0.0.1:8000/api/v1/dashboards/recent-events" | jq

# Pending review queue
curl -s "http://127.0.0.1:8000/api/v1/dashboards/review-queue" | jq
```

### 7) What to point out during the demo

- `events`: includes **Amgen ABP 206**, **Henlius HLX18**, and **India launch-style** narrative.
- `summary`: shows total volume and split by review status/traffic light.
- `top-threats`: surfaces highest-risk rows first for decision support.
- `recent-events`: confirms latest activity ordering.
- `review-queue`: highlights pending analyst workload.

Optional short review action in Swagger:
- Approve/reject one event via `/api/v1/events/{event_id}/approve` or `/reject`.
- Refresh `/dashboards/summary` and `/dashboards/review-queue` to show state change.

---

## Workflow Automation

Biosi supports three API-driven workflow patterns for operational automation:

- Daily ClinicalTrials.gov ingestion
- Approved Red event alerting
- Weekly summary digest

The current documented implementation uses n8n for scheduling, API calls, filtering, and notifications. The workflow logic is API-first and remains portable to other orchestration tools (for example Make, Airflow, GitHub Actions, or scripts) if tooling changes later.

> The Biosi API is permanently hosted on Railway. n8n workflows call https://biosi-production.up.railway.app directly — no ngrok or local server required.

For detailed node-by-node setup, payloads, filter logic, failure handling, and manual test steps, see [docs/n8n-workflows.md](docs/n8n-workflows.md).

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
| `PORT` | No | `8000` | Auto-injected by Railway for the uvicorn bind port |
| `SECRET_KEY` | **Yes** | — | Min 32-char random string |
| `DATABASE_URL` | **Yes** | — | Pooled asyncpg URL for runtime |
| `DATABASE_URL_DIRECT` | **Yes** | — | Direct psycopg URL for migrations |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:8000` | Comma-separated allowed origins |
| `OPENROUTER_API_KEY` | No | — | OpenRouter key (Milestone 3+) |
| `OPENROUTER_MODEL_PRIMARY` | No | `google/gemini-2.0-flash-001` | Primary LLM model |
| `OPENROUTER_MODEL_FALLBACK` | No | `anthropic/claude-3.5-haiku` | Fallback LLM model |
| `OPENROUTER_BASE_URL` | No | `https://openrouter.ai/api/v1/chat/completions` | OpenRouter chat-completions endpoint |
| `OPENROUTER_TIMEOUT_SECONDS` | No | `45` | Timeout for OpenRouter HTTP calls |
| `CLINICALTRIALS_BASE_URL` | No | `https://clinicaltrials.gov/api/v2/studies` | ClinicalTrials API v2 base |
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
