"""Tests for GET /api/v1/health."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.api.deps import get_db
from app.main import app


@pytest.fixture()
def mock_db():
    """Yield a mocked async DB session and clean up overrides after the test."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    yield session
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.anyio
async def test_health_returns_ok(mock_db, client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body.keys()) == {"status"}


@pytest.mark.anyio
async def test_health_response_schema(mock_db, client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    body = response.json()
    assert set(body.keys()) == {"status"}
