# Testing and local checks

Use these commands from the repository root (Biosi).

- Create/activate venv (once): `python3 -m venv .venv && source .venv/bin/activate`
- Install runtime deps: `./.venv/bin/python -m pip install -r requirements.txt`
- Install dev/test deps: `./.venv/bin/python -m pip install -r requirements-dev.txt`
- Apply migrations: `./.venv/bin/python -m alembic upgrade head`
- Check migration head/current revision: `./.venv/bin/python -m alembic current`
- Seed reference data (idempotent): `./.venv/bin/python -m app.db.seed`
- Seed demo events/competitors (idempotent): `./.venv/bin/python -m scripts.seeddemodata`
- Run API locally: `./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- Run all automated tests: `./.venv/bin/python -m pytest -q`

## API coverage in automated tests

- Health: `/api/v1/health` status + response shape.
- Events: list, detail (valid + invalid ID), create, update, and 422 validation path.
- Reviews: list and create review linked to an existing event.
- Dashboards: summary shape, top-threat ordering, recent-events recency ordering, review-queue pending status.
- Jobs: ClinicalTrials ingestion contract + repeat-run counter sanity; press-release ingestion happy path when OpenRouter key exists, otherwise explicit 422 config-error assertion.
