"""Tests for GET /api/v1/health."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body.keys()) == {"status"}


@pytest.mark.anyio
async def test_health_response_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    body = response.json()
    assert set(body.keys()) == {"status"}
