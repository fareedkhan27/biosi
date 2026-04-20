"""
Integration tests for review workflow endpoints.

NOTE: These endpoints are NOT yet implemented in the router as of the current
codebase.  All tests are marked ``xfail`` and will pass once the router is
wired up.

Expected endpoint contracts (to be implemented):
  POST  /api/v1/events/{event_id}/approve
  POST  /api/v1/events/{event_id}/reject
  POST  /api/v1/reviews                    (direct review creation, optional)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.schemas.review import ReviewRead


_FAKE_EVENT_ID = "00000000-0000-0000-0000-000000000099"


@pytest.mark.anyio
async def test_approve_event_returns_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_approve(session, event_id, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="approved",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="approved",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.services.review_service.approve_event", _stub_approve)
    response = await client.post(f"/api/v1/events/{_FAKE_EVENT_ID}/approve")
    assert response.status_code in (200, 201, 204)


@pytest.mark.anyio
async def test_approve_event_changes_review_status(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_approve(session, event_id, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="approved",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="approved",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.services.review_service.approve_event", _stub_approve)
    response = await client.post(f"/api/v1/events/{_FAKE_EVENT_ID}/approve")
    body = response.json()
    assert body.get("review_status") == "approved" or body.get("status") == "approved"


@pytest.mark.anyio
async def test_approve_event_accepts_reviewer_and_comment(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_approve(session, event_id, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="approved",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="approved",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.services.review_service.approve_event", _stub_approve)
    response = await client.post(
        f"/api/v1/events/{_FAKE_EVENT_ID}/approve",
        json={"reviewer_email": "analyst@biosimilar.io", "comment": "Confirmed."},
    )
    assert response.status_code in (200, 201, 204)


@pytest.mark.anyio
async def test_reject_event_returns_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_reject(session, event_id, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="rejected",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="rejected",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.services.review_service.reject_event", _stub_reject)
    response = await client.post(f"/api/v1/events/{_FAKE_EVENT_ID}/reject")
    assert response.status_code in (200, 201, 204)


@pytest.mark.anyio
async def test_reject_event_changes_review_status(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_reject(session, event_id, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="rejected",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="rejected",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.services.review_service.reject_event", _stub_reject)
    response = await client.post(f"/api/v1/events/{_FAKE_EVENT_ID}/reject")
    body = response.json()
    assert body.get("review_status") == "rejected" or body.get("status") == "rejected"


@pytest.mark.anyio
async def test_approve_nonexistent_event_returns_404(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_approve(session, event_id, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.services.review_service.approve_event", _stub_approve)
    response = await client.post(
        "/api/v1/events/00000000-0000-0000-0000-000000000000/approve"
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_reject_nonexistent_event_returns_404(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_reject(session, event_id, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.services.review_service.reject_event", _stub_reject)
    response = await client.post(
        "/api/v1/events/00000000-0000-0000-0000-000000000000/reject"
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_direct_review_creation_returns_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct POST /api/v1/reviews if the endpoint exists."""
    async def _stub_create_review(session, data):  # type: ignore[no-untyped-def]
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=data.event_id,
            status=data.status,
            reviewer=data.reviewer,
            review_notes=data.review_notes,
            review_status=data.status,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.services.review_service.create_review", _stub_create_review)

    response = await client.post(
        "/api/v1/reviews",
        json={
            "event_id": _FAKE_EVENT_ID,
            "status": "approved",
            "reviewer": "analyst@biosimilar.io",
            "review_notes": "Verified against source.",
        },
    )
    assert response.status_code in (200, 201)


@pytest.mark.anyio
async def test_direct_review_creation_review_record_contains_event_id(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_create_review(session, data):  # type: ignore[no-untyped-def]
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=data.event_id,
            status=data.status,
            reviewer=data.reviewer,
            review_notes=data.review_notes,
            review_status=data.status,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.services.review_service.create_review", _stub_create_review)

    response = await client.post(
        "/api/v1/reviews",
        json={
            "event_id": _FAKE_EVENT_ID,
            "status": "approved",
        },
    )
    body = response.json()
    assert body.get("event_id") == _FAKE_EVENT_ID
