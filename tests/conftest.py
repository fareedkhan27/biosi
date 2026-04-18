"""
Pytest configuration and shared fixtures.

Set APP_ENV=test in conftest so Settings picks it up before any import.
The DATABASE_URL / DATABASE_URL_DIRECT envvars are expected to be set
in the CI environment (see .github/workflows/ci.yml) or in a local
.env.test file (not committed).
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Force test environment BEFORE app imports
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")

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
