# Biosi Codebase Structure

Generated on: 2026-04-21

This map summarizes the **current repository structure** and the **intent** of each major file/folder in one line.

---

## Root

- `.github/` — GitHub automation/config (CI workflows, PR template, Copilot repo instructions).
- `.claude/` — Local Claude/assistant configuration artifacts.
- `.vscode/` — Workspace/editor settings for VS Code.
- `.venv/` — Local Python virtual environment (runtime dependencies).
- `alembic/` — Database migration environment and migration version scripts.
- `app/` — Main FastAPI application package (API, services, schemas, models, core infra).
- `docker/` — Container build files for running the API in Docker.
- `docs/` — Product/automation documentation (including n8n workflow contracts).
- `scripts/` — Utility scripts for reseeding/reingesting operational data.
- `tests/` — Unit/integration/API contract test suites and fixtures.
- `README.md` — Project overview, setup, and usage guide.
- `TESTING.md` — Testing-specific instructions and conventions.
- `main.py` — Top-level ASGI entrypoint shim for `uvicorn main:app` compatibility.
- `alembic.ini` — Alembic runtime configuration.
- `pyproject.toml` — Python project/tool configuration (lint/format/type/test settings).
- `requirements.txt` — Runtime Python dependencies.
- `requirements-dev.txt` — Development/test/lint/type-check dependencies.
- `docker-compose.yml` — Local multi-service orchestration (API + infra).
- `railway.toml` — Railway deployment configuration.
- `start.sh` — Startup helper script for local/deploy runs.
- `__init__.py` — Root package marker.
- `coverage.xml` — Generated code coverage report artifact.

---

## .github

- `.github/workflows/ci.yml` — CI pipeline (ruff, mypy, alembic migration, pytest).
- `.github/PULL_REQUEST_TEMPLATE.md` — Standard PR checklist/template.
- `.github/copilot-instructions.md` — Repo-specific coding instructions for assistants.

---

## Alembic

- `alembic/env.py` — Alembic migration environment wiring and metadata loading.
- `alembic/script.py.mako` — Template used when generating new migration files.
- `alembic/versions/` — Ordered schema migration history for Postgres.
- `alembic/versions/20260418_0001_initial_schema.py` — Initial schema creation migration.
- `alembic/versions/20260418_0002_add_event_scoring_columns.py` — Adds event scoring-related DB columns.
- `alembic/versions/20260420_0003_add_indication_to_events.py` — Adds indication support to events schema.

---

## App package

- `app/main.py` — FastAPI app factory, middleware, exception handlers, router registration.

### app/api

- `app/api/deps.py` — Shared FastAPI dependencies (including DB session provider).
- `app/api/v1/` — Versioned API endpoints grouped by domain.
- `app/api/v1/router.py` — Aggregates all v1 routers under `/api/v1`.
- `app/api/v1/health.py` — Health and observability endpoints.
- `app/api/v1/jobs.py` — Ingestion job endpoints (clinicaltrials, press-release, n8n webhook).
- `app/api/v1/events.py` — Event CRUD endpoints.
- `app/api/v1/reviews.py` — Review workflow endpoints (approve/reject/list).
- `app/api/v1/dashboards.py` — Dashboard summary/top-threat/recent/review-queue endpoints.
- `app/api/v1/intelligence.py` — Intelligence/weekly digest endpoints.

### app/core

- `app/core/config.py` — Centralized Pydantic settings/env var definitions.
- `app/core/db.py` — Database engine/session setup and lifecycle helpers.
- `app/core/exceptions.py` — Domain-specific custom exception types.
- `app/core/logging.py` — Logging configuration setup.

### app/db

- `app/db/session.py` — Async SQLAlchemy session factory helpers.
- `app/db/url.py` — Database URL normalization/adaptation for async/sync drivers.
- `app/db/seed.py` — Seed entrypoint for initializing baseline data.
- `app/db/seeds.py` — Seed orchestration/registry helpers.
- `app/db/seed_data.py` — Main domain seed dataset loader.
- `app/db/seed_competitors.py` — Biosimilar competitor seed data loader.

### app/models

- `app/models/base.py` — Declarative base and ORM metadata anchor.
- `app/models/mixins.py` — Reusable ORM mixins (timestamps/common fields).
- `app/models/competitor.py` — Competitor entity model.
- `app/models/biosimilar_competitor.py` — Enriched competitor profile model used in scoring.
- `app/models/source.py` — Ingestion source registry model.
- `app/models/source_document.py` — Source document store with idempotency keys and payloads.
- `app/models/event.py` — Core intelligence event model with score/review fields.
- `app/models/review.py` — Review decision/audit trail model.
- `app/models/scoring_rule.py` — Scoring rule/policy persistence model.

### app/schemas

- `app/schemas/health.py` — Health endpoint response schema(s).
- `app/schemas/ingestion.py` — Request/response schemas for ingestion and webhook jobs.
- `app/schemas/event.py` — Event create/read/update API schemas.
- `app/schemas/review.py` — Review workflow API schemas.
- `app/schemas/dashboard.py` — Dashboard payload schemas and typed contract models.
- `app/schemas/intelligence.py` — Weekly digest/intelligence response schemas.

### app/services

- `app/services/clinicaltrials_service.py` — ClinicalTrials.gov ingestion, normalization, and upsert logic.
- `app/services/press_release_service.py` — Press-release extraction ingestion and event/source upsert flow.
- `app/services/extraction_service.py` — LLM extraction contract, validation, and prompt construction.
- `app/services/openrouter_service.py` — OpenRouter HTTP client wrapper with fallback/error handling.
- `app/services/event_service.py` — Event CRUD and score recomputation logic.
- `app/services/review_service.py` — Approval/rejection/review persistence workflow logic.
- `app/services/scoring_service.py` — Deterministic multi-factor threat scoring + traffic-light classification.
- `app/services/dashboard_service.py` — Dashboard aggregation, filtering, normalization, and dedupe queries.
- `app/services/intelligence_interpreter.py` — Deterministic interpretation text generation for event insights.

---

## Docs

- `docs/n8n-workflows.md` — Source-of-truth contract for n8n workflows and API endpoint dependencies.
- `docs/automation-templates.md` — Automation template guidance for orchestration flows.
- `docs/# Biosi Demo End-to-End Build Plan.md` — End-to-end product/demo implementation plan.
- `docs/Gmail - Biosi Weekly Digest .pdf` — Sample/report artifact for weekly digest output.
- `docs/biosi_improvement_recommendations.pdf` — Product/engineering recommendations artifact.

---

## Docker

- `docker/Dockerfile` — API container build instructions.

---

## Scripts

- `scripts/purge_and_reingest.py` — Utility script to clear and re-run ingestion datasets.
- `scripts/seeddemodata.py` — Helper script to seed demo/test-friendly data.

---

## Tests

- `tests/conftest.py` — Shared top-level pytest fixtures/utilities.
- `tests/helpers/` — Test helper factories/utilities for reusable fixtures.
- `tests/helpers/factories.py` — Object factory helpers for deterministic test data.
- `tests/api/` — API-level test package namespace.
- `tests/api/v1/` — Versioned API tests grouped by endpoint domain.
- `tests/integration/` — Integration/contract tests using dependency overrides and mocked async DB.
- `tests/integration/conftest.py` — Integration fixture wiring (`get_db` override + async client).
- `tests/integration/test_api_v1_contracts.py` — Public API/OpenAPI contract tests.
- `tests/integration/test_n8n_contracts.py` — n8n response-shape compatibility and workflow contract tests.
- `tests/integration/test_health.py` — Health endpoint behavior tests.
- `tests/integration/test_events_api.py` — Events API endpoint behavior tests.
- `tests/integration/test_reviews_api.py` — Reviews endpoint behavior tests.
- `tests/integration/test_jobs_clinicaltrials.py` — ClinicalTrials job endpoint tests.
- `tests/integration/test_jobs_press_release.py` — Press-release job endpoint tests.
- `tests/integration/test_dashboard_summary.py` — Dashboard summary endpoint tests.
- `tests/integration/test_event_review_scoring_flow.py` — End-to-end event → scoring → review flow tests.
- `tests/services/` — Service-layer logic tests by module.
- `tests/services/test_clinicaltrials_service.py` — ClinicalTrials service logic tests.
- `tests/services/test_press_release_service.py` — Press-release ingestion service tests.
- `tests/services/test_extraction_service.py` — Extraction and schema-validation tests.
- `tests/services/test_event_service.py` — Event CRUD and recompute tests.
- `tests/services/test_review_service.py` — Review workflow service tests.
- `tests/services/test_dashboard_service.py` — Dashboard aggregation/filtering tests.
- `tests/services/test_scoring_service.py` — Threat scoring and traffic-light mapping tests.
- `tests/services/test_intelligence_interpreter.py` — Insight interpretation output tests.
- `tests/test_api_testclient_integration.py` — End-to-end API client integration sanity checks.
- `tests/test_seed_data.py` — Seed-data integrity and bootstrap tests.
- `tests/test_services.py` — Cross-service behavior smoke tests.
- `tests/Biosimilar.code-workspace` — Workspace file used for editor/test setup context.

---

## Generated/cache folders (non-source)

- `__pycache__/` (multiple locations) — Python bytecode cache artifacts.
- `.pytest_cache/` — Pytest run cache/state.
- `.ruff_cache/` — Ruff lint/format cache.
- `.DS_Store` files — macOS Finder metadata files.

---

## High-level architecture intent (one-line)

- **Router → Service → Async SQLAlchemy → Postgres Models/Schemas** — core request lifecycle and layering used across the codebase.
