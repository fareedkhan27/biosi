"""
Pytest configuration and shared fixtures.

Set APP_ENV=test in conftest so Settings picks it up before any import.
The DATABASE_URL / DATABASE_URL_DIRECT envvars are expected to be set
in the CI environment (see .github/workflows/ci.yml) or in a local
.env.test file (not committed).
"""

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Force test environment BEFORE app imports
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")

def _project_has_db_env_file() -> bool:
    project_root = Path(__file__).resolve().parents[1]
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

from app.main import app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
async def client() -> AsyncClient:
    """Return an HTTPX async test client wired to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
