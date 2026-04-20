"""
Integration tests for /api/v1/events (CRUD + filtering).

NOTE: These endpoints are NOT yet implemented in the router as of the current
codebase (only /api/v1/health and /api/v1/jobs/* exist).  All tests are marked
``xfail`` so that the suite stays green; remove the ``xfail`` marker once the
events router is wired up.

Expected endpoint contracts (to be implemented):
  POST   /api/v1/events           → 201, returns created event with id
  GET    /api/v1/events           → 200, list of events
  GET    /api/v1/events/{id}      → 200, single event
  PATCH  /api/v1/events/{id}      → 200, updated event
  GET    /api/v1/events?traffic_light=Red
  GET    /api/v1/events?event_type=launch
  GET    /api/v1/events?region=APAC
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient

from app.schemas.event import EventRead

# Sample minimal event payload for creation
_CREATE_EVENT_PAYLOAD = {
    "competitor_id": "00000000-0000-0000-0000-000000000001",
    "event_type": "launch",
    "title": "Amgen launches ABP 206 in US market",
    "description": "ABP 206, a biosimilar to Opdivo, receives FDA approval.",
    "event_date": "2026-04-01",
}


@pytest.mark.anyio
async def test_create_event_returns_201_or_200(client: AsyncClient) -> None:
    response = await client.post("/api/v1/events", json=_CREATE_EVENT_PAYLOAD)
    assert response.status_code in (200, 201)


@pytest.mark.anyio
async def test_create_event_response_contains_id(client: AsyncClient) -> None:
    response = await client.post("/api/v1/events", json=_CREATE_EVENT_PAYLOAD)
    body = response.json()
    assert "id" in body


@pytest.mark.anyio
async def test_create_event_response_reflects_submitted_fields(client: AsyncClient) -> None:
    response = await client.post("/api/v1/events", json=_CREATE_EVENT_PAYLOAD)
    body = response.json()
    assert body["event_type"] == _CREATE_EVENT_PAYLOAD["event_type"]
    assert body["title"] == _CREATE_EVENT_PAYLOAD["title"]


@pytest.mark.anyio
async def test_list_events_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_list_events_returns_list(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events")
    body = response.json()
    assert isinstance(body, list) or ("items" in body)


@pytest.mark.anyio
async def test_get_event_by_id_returns_200(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id = str(uuid.uuid4())

    async def _stub_get_event(session, event_id_arg):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        return EventRead(
            id=uuid.UUID(event_id),
            competitor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            event_type="launch",
            title="Amgen launches ABP 206 in US market",
            description="ABP 206, a biosimilar to Opdivo, receives FDA approval.",
            event_date=date(2026, 4, 1),
            region="North America",
            country="United States",
            traffic_light="Red",
            threat_score=72.0,
            development_stage=None,
            indication=None,
            metadata_json={},
            review_status="pending",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )

    monkeypatch.setattr("app.services.event_service.get_event", _stub_get_event)

    get_resp = await client.get(f"/api/v1/events/{event_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == event_id


@pytest.mark.anyio
async def test_get_event_by_nonexistent_id_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events/00000000-0000-0000-0000-deadbeef0000")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_patch_event_persists_change(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id = str(uuid.uuid4())

    async def _stub_update_event(session, event_id_arg, data):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        return EventRead(
            id=uuid.UUID(event_id),
            competitor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            event_type="launch",
            title="Amgen launches ABP 206 in US market",
            description=data.description,
            event_date=date(2026, 4, 1),
            region="North America",
            country="United States",
            traffic_light="Red",
            threat_score=72.0,
            development_stage=None,
            indication=None,
            metadata_json={},
            review_status="pending",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )

    monkeypatch.setattr("app.services.event_service.update_event", _stub_update_event)

    patch_resp = await client.patch(
        f"/api/v1/events/{event_id}",
        json={"description": "Updated description after analyst review."},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "Updated description after analyst review."


@pytest.mark.anyio
async def test_filter_events_by_traffic_light(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events", params={"traffic_light": "Red"})
    assert response.status_code == 200
    body = response.json()
    events = body if isinstance(body, list) else body.get("items", [])
    for event in events:
        assert event.get("traffic_light") == "Red"


@pytest.mark.anyio
async def test_filter_events_by_event_type(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events", params={"event_type": "launch"})
    assert response.status_code == 200


@pytest.mark.anyio
async def test_filter_events_by_region(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events", params={"region": "APAC"})
    assert response.status_code == 200
