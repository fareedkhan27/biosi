"""
Integration-test fixtures.

Key design decisions
--------------------
* ``get_db`` is overridden via FastAPI's ``dependency_overrides`` so no real
  Postgres connection is ever opened for tests that mock service methods.
* ``mock_db_session`` is an ``AsyncMock``; its execute/add/flush/commit methods
  are all no-ops unless a test configures them explicitly.
* The ``client`` fixture defined here shadows the root conftest ``client`` for
  every test inside ``tests/integration/``.
* Service-layer monkeypatching (via ``monkeypatch``) is the primary isolation
  strategy; DB-level assertions use the mock session's call records.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# Force test env before any app-level import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")

def _project_has_db_env_file() -> bool:
  project_root = Path(__file__).resolve().parents[2]
  env_file = project_root / ".env"
  if not env_file.exists():
    return False

  content = env_file.read_text(encoding="utf-8", errors="ignore")
  return "DATABASE_URL=" in content and "DATABASE_URL_DIRECT=" in content


# Provide fallback DB URLs only when neither env vars nor .env DB values exist.
if not _project_has_db_env_file():
  os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/biosi_test",
  )
  os.environ.setdefault(
    "DATABASE_URL_DIRECT",
    "postgresql+asyncpg://test:test@localhost:5432/biosi_test",
  )

from app.api.deps import get_db  # noqa: E402  (must come after env setup)
from app.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Return a fully-mocked async SQLAlchemy session."""
    session = AsyncMock()
    session.add = MagicMock(return_value=None)
    # Make commit/flush/rollback no-ops
    session.commit = AsyncMock(return_value=None)
    session.flush = AsyncMock(return_value=None)
    session.rollback = AsyncMock(return_value=None)
    session.close = AsyncMock(return_value=None)
    # execute() returns a result object; tests override as needed.
    # scalar_one_or_none() — used by single-row lookups (get/upsert)
    # scalars().all()      — used by list queries (list_events, dashboards, reviews)
    default_result = MagicMock()
    default_result.scalar_one_or_none = MagicMock(return_value=None)
    default_result.scalars.return_value.all.return_value = []
    default_result.all.return_value = []
    session.execute = AsyncMock(return_value=default_result)
    return session


@pytest.fixture()
async def client(mock_db_session: AsyncMock) -> AsyncClient:  # type: ignore[override]
    """
    HTTPX async test client wired to the FastAPI app with ``get_db`` overridden
    so that no actual Postgres connection is required.
    """

    async def _override_get_db():  # type: ignore[return]
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
