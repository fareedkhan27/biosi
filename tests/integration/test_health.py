"""Integration tests for health endpoints."""

from __future__ import annotations
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_status_is_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    body = response.json()
    assert body["status"] == "ok"


@pytest.mark.anyio
async def test_health_response_has_required_keys(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    body = response.json()
    assert set(body.keys()) == {"status"}


@pytest.mark.anyio
async def test_health_response_has_no_extra_keys(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    body = response.json()
    assert set(body.keys()) == {"status"}


@pytest.mark.anyio
async def test_health_n8n_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/n8n")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_n8n_response_shape(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/health/n8n")).json()
    assert set(body.keys()) == {"status", "db", "openrouter", "version", "timestamp"}
    assert body["status"] == "ok"
    assert body["db"] == "connected"


@pytest.mark.anyio
async def test_health_is_idempotent(client: AsyncClient) -> None:
    r1 = await client.get("/api/v1/health")
    r2 = await client.get("/api/v1/health")
    assert r1.status_code == r2.status_code
    assert r1.json() == r2.json()


@pytest.mark.anyio
async def test_health_content_type_is_json(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.anyio
async def test_health_returns_503_when_db_down(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """If database connectivity fails, /health must return 503."""
    mock_db_session.execute = AsyncMock(side_effect=ConnectionError("DB is down"))
    response = await client.get("/api/v1/health")
    assert response.status_code == 503
    assert "Database connectivity check failed" in response.json()["detail"]
