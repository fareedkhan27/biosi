# Copilot instructions for Biosi

## Big picture (read this first)
- Biosi is an async FastAPI API for biosimilar competitive-intelligence ingestion, review, and dashboarding.
- Request flow is: router -> service -> SQLAlchemy async session -> Postgres models/schemas.
- Primary entrypoint is [app/main.py](../app/main.py); both `uvicorn app.main:app` and `uvicorn main:app` are supported via [main.py](../main.py).
- API surface is aggregated in [app/api/v1/router.py](../app/api/v1/router.py) under `/api/v1`.

## Core domains and boundaries
- Ingestion jobs live in [app/api/v1/jobs.py](../app/api/v1/jobs.py) and delegate to:
  - [app/services/clinicaltrials_service.py](../app/services/clinicaltrials_service.py)
  - [app/services/press_release_service.py](../app/services/press_release_service.py)
- `PressReleaseIngestionService` extracts with OpenRouter via [app/services/extraction_service.py](../app/services/extraction_service.py) -> [app/services/openrouter_service.py](../app/services/openrouter_service.py).
- Event CRUD and scoring logic are in [app/services/event_service.py](../app/services/event_service.py) + [app/services/scoring_service.py](../app/services/scoring_service.py).
- Review state transitions (`pending/approved/rejected`) are in [app/services/review_service.py](../app/services/review_service.py).
- Dashboard queries are in [app/services/dashboard_service.py](../app/services/dashboard_service.py), designed to support n8n contracts in [docs/n8n-workflows.md](../docs/n8n-workflows.md).

## Project-specific conventions (important)
- `Event.metadata_json` (DB column name `metadata`) stores many business fields (`region`, `country`, `development_stage`, `confidence_score`) even when API exposes them as top-level convenience fields; preserve this mapping.
- Threat score + traffic light should be recomputed when scoring inputs change (`event_type`, stage, confidence, geography); see `_scoring_inputs_changed` in [app/services/event_service.py](../app/services/event_service.py).
- Ingestion is idempotent by upsert patterns:
  - source documents keyed by `(source_id, external_id)` in [app/models/source_document.py](../app/models/source_document.py)
  - events keyed by `(competitor_id, source_document_id, event_type)` in ingestion services.
- Runtime DB uses async URL conversion in [app/db/url.py](../app/db/url.py); Alembic uses direct psycopg URL in [alembic/env.py](../alembic/env.py).
- Settings are strict and centralized in [app/core/config.py](../app/core/config.py); avoid scattered `os.getenv` usage.

## Developer workflows that match CI
- Setup and env: use a single venv at project root (`Biosi/.venv`) and `.env` values for `DATABASE_URL`, `DATABASE_URL_DIRECT`, `SECRET_KEY`.
- Apply migrations before local/API tests: `alembic upgrade head` (same as CI in [.github/workflows/ci.yml](workflows/ci.yml)).
- Run API: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
- Quality gates (match CI/tooling): `ruff check .`, `ruff format --check .`, `mypy app`, `pytest`.

## Testing patterns in this repo
- Integration tests override DB dependency (`get_db`) with mocked async session; see [tests/integration/conftest.py](../tests/integration/conftest.py).
- Endpoint contract tests often monkeypatch service methods instead of hitting real externals; see [tests/integration/test_api_v1_contracts.py](../tests/integration/test_api_v1_contracts.py).
- n8n compatibility is enforced via strict response-shape tests in [tests/integration/test_n8n_contracts.py](../tests/integration/test_n8n_contracts.py); avoid breaking response fields/types for jobs and dashboard endpoints.

## When adding features
- Add/modify route in `app/api/v1/*`, implement business logic in `app/services/*`, and keep schemas in `app/schemas/*`.
- If model shape changes: update SQLAlchemy model + Alembic migration + Pydantic schemas + affected contract tests together.
- Preserve OpenAPI tags and endpoint contracts used by automation consumers.
