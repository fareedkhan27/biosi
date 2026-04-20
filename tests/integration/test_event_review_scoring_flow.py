from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient

from app.schemas.event import EventRead
from app.schemas.review import ReviewRead
from app.services.extraction_service import ExtractedEvent
from app.services.press_release_service import PressReleaseIngestionResult


@pytest.mark.anyio
async def test_create_score_approve_and_review_list_flow(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    competitor_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    created_at = datetime(2026, 4, 18, tzinfo=timezone.utc)
    state = {"review_status": "pending"}

    async def _stub_create_event(session, data):  # type: ignore[no-untyped-def]
        return EventRead(
            id=uuid.UUID(event_id),
            competitor_id=uuid.UUID(competitor_id),
            event_type=data.event_type,
            title=data.title,
            description=data.description,
            event_date=date(2026, 4, 18),
            region="North America",
            country="United States",
            traffic_light="Amber",
            threat_score=55.0,
            development_stage="Phase 3",
            indication=None,
            metadata_json={"confidence_score": 78},
            review_status=state["review_status"],
            created_at=created_at,
        )

    async def _stub_get_event(session, event_id_arg):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        return EventRead(
            id=uuid.UUID(event_id),
            competitor_id=uuid.UUID(competitor_id),
            event_type="trial_phase_change",
            title="ABP 206 moved to Phase 3",
            description="Milestone announcement",
            event_date=date(2026, 4, 18),
            region="North America",
            country="United States",
            traffic_light="Amber",
            threat_score=55.0,
            development_stage="Phase 3",
            indication=None,
            metadata_json={"confidence_score": 78},
            review_status=state["review_status"],
            created_at=created_at,
        )

    async def _stub_approve_event(session, event_id_arg, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        state["review_status"] = "approved"
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="approved",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="approved",
            created_at=created_at,
        )

    async def _stub_list_reviews(session):  # type: ignore[no-untyped-def]
        return [
            ReviewRead(
                id=uuid.uuid4(),
                event_id=uuid.UUID(event_id),
                status=state["review_status"],
                reviewer="analyst@biosi.io",
                review_notes="Looks good",
                review_status=state["review_status"],
                created_at=created_at,
            )
        ]

    monkeypatch.setattr("app.services.event_service.create_event", _stub_create_event)
    monkeypatch.setattr("app.services.event_service.get_event", _stub_get_event)
    monkeypatch.setattr("app.services.review_service.approve_event", _stub_approve_event)
    monkeypatch.setattr("app.services.review_service.list_reviews", _stub_list_reviews)

    create_payload = {
        "competitor_id": competitor_id,
        "event_type": "trial_phase_change",
        "title": "ABP 206 moved to Phase 3",
        "description": "Milestone announcement",
        "event_date": "2026-04-18",
        "region": "North America",
        "country": "United States",
        "development_stage": "Phase 3",
        "metadata_json": {"confidence_score": 78},
    }

    created = await client.post("/api/v1/events", json=create_payload)
    assert created.status_code == 201
    created_body = created.json()

    assert isinstance(created_body.get("id"), str) and created_body["id"]
    assert created_body.get("threat_score") is not None
    assert created_body.get("traffic_light") in {"Green", "Amber", "Red"}
    assert created_body.get("review_status") == "pending"

    event_id = created_body["id"]

    fetched = await client.get(f"/api/v1/events/{event_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()

    assert fetched_body.get("threat_score") == created_body.get("threat_score")
    assert fetched_body.get("traffic_light") == created_body.get("traffic_light")

    approved = await client.post(
        f"/api/v1/events/{event_id}/approve",
        json={"reviewer_email": "analyst@biosi.io", "comment": "Looks good"},
    )
    assert approved.status_code == 200
    approved_body = approved.json()

    assert approved_body.get("event_id") == event_id
    assert approved_body.get("status") == "approved"

    fetched_after_approve = await client.get(f"/api/v1/events/{event_id}")
    assert fetched_after_approve.status_code == 200
    assert fetched_after_approve.json().get("review_status") == "approved"

    reviews = await client.get("/api/v1/reviews")
    assert reviews.status_code == 200
    reviews_body = reviews.json()
    assert isinstance(reviews_body, list)

    matching = [r for r in reviews_body if r.get("event_id") == event_id]
    assert matching
    assert matching[0].get("status") == "approved"


@pytest.mark.anyio
async def test_reject_flow_keeps_event_stored_and_logs_review(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    competitor_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    created_at = datetime(2026, 4, 18, tzinfo=timezone.utc)
    state = {"review_status": "pending"}

    async def _stub_create_event(session, data):  # type: ignore[no-untyped-def]
        return EventRead(
            id=uuid.UUID(event_id),
            competitor_id=uuid.UUID(competitor_id),
            event_type=data.event_type,
            title=data.title,
            description=data.description,
            event_date=date(2026, 4, 18),
            region="Europe",
            country="Germany",
            traffic_light="Green",
            threat_score=30.0,
            development_stage="Phase 1",
            indication=None,
            metadata_json={"confidence_score": 35},
            review_status=state["review_status"],
            created_at=created_at,
        )

    async def _stub_get_event(session, event_id_arg):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        return EventRead(
            id=uuid.UUID(event_id),
            competitor_id=uuid.UUID(competitor_id),
            event_type="clinical_trial_update",
            title="Early signal under review",
            description="Potential low-confidence signal",
            event_date=date(2026, 4, 18),
            region="Europe",
            country="Germany",
            traffic_light="Green",
            threat_score=30.0,
            development_stage="Phase 1",
            indication=None,
            metadata_json={"confidence_score": 35},
            review_status=state["review_status"],
            created_at=created_at,
        )

    async def _stub_reject_event(session, event_id_arg, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        state["review_status"] = "rejected"
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="rejected",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="rejected",
            created_at=created_at,
        )

    async def _stub_list_reviews(session):  # type: ignore[no-untyped-def]
        return [
            ReviewRead(
                id=uuid.uuid4(),
                event_id=uuid.UUID(event_id),
                status=state["review_status"],
                reviewer="analyst@biosi.io",
                review_notes="Insufficient evidence",
                review_status=state["review_status"],
                created_at=created_at,
            )
        ]

    monkeypatch.setattr("app.services.event_service.create_event", _stub_create_event)
    monkeypatch.setattr("app.services.event_service.get_event", _stub_get_event)
    monkeypatch.setattr("app.services.review_service.reject_event", _stub_reject_event)
    monkeypatch.setattr("app.services.review_service.list_reviews", _stub_list_reviews)

    create_payload = {
        "competitor_id": competitor_id,
        "event_type": "clinical_trial_update",
        "title": "Early signal under review",
        "description": "Potential low-confidence signal",
        "event_date": "2026-04-18",
        "region": "Europe",
        "country": "Germany",
        "development_stage": "Phase 1",
        "metadata_json": {"confidence_score": 35},
    }

    created = await client.post("/api/v1/events", json=create_payload)
    assert created.status_code == 201
    returned_event_id = created.json()["id"]
    assert returned_event_id == event_id

    rejected = await client.post(
        f"/api/v1/events/{event_id}/reject",
        json={"reviewer_email": "analyst@biosi.io", "comment": "Insufficient evidence"},
    )
    assert rejected.status_code == 200
    assert rejected.json().get("status") == "rejected"

    fetched_after_reject = await client.get(f"/api/v1/events/{event_id}")
    assert fetched_after_reject.status_code == 200
    assert fetched_after_reject.json().get("review_status") == "rejected"

    reviews = await client.get("/api/v1/reviews")
    assert reviews.status_code == 200
    matching = [r for r in reviews.json() if r.get("event_id") == event_id]
    assert matching
    assert matching[0].get("status") == "rejected"


@pytest.mark.anyio
async def test_press_release_ingestion_creates_pending_event_visible_in_events_list(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid.uuid4().hex[:10]
    expected_summary = f"Integration pending review check {token}"

    async def _stub_ingest_press_release(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return PressReleaseIngestionResult(
            extracted_event=ExtractedEvent(
            competitor_name=f"IntegrationCo {token}",
            asset_code=f"ABP-{token.upper()}",
            molecule_name="Nivolumab",
            reference_brand="Opdivo",
            event_type="clinical_trial_update",
            event_subtype="phase_advancement",
            development_stage="Phase 3",
            indication="NSCLC",
            region="North America",
            country="United States",
            event_date="2026-04-18",
            summary=expected_summary,
            evidence_excerpt="First patient dosed.",
            confidence_score=80,
            ),
            source_document_created=True,
            source_document_updated=False,
            event_created=True,
            event_updated=False,
        )

    async def _stub_list_events(session, **kwargs):  # type: ignore[no-untyped-def]
        return [
            EventRead(
                id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
                event_type="clinical_trial_update",
                title=f"IntegrationCo {token}: update",
                description=expected_summary,
                event_date=date(2026, 4, 18),
                region="North America",
                country="United States",
                traffic_light="Amber",
                threat_score=52.0,
                development_stage="Phase 3",
                indication="NSCLC",
                metadata_json={"confidence_score": 80},
                review_status="pending",
                created_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
            )
        ]

    monkeypatch.setattr(
        "app.services.press_release_service.PressReleaseIngestionService.ingest_press_release",
        _stub_ingest_press_release,
    )
    monkeypatch.setattr("app.services.event_service.list_events", _stub_list_events)

    response = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={
            "text": f"Press release body {token}",
            "source_url": f"https://example.com/pr/{token}",
        },
    )
    assert response.status_code == 200

    events = await client.get("/api/v1/events")
    assert events.status_code == 200
    events_body = events.json()
    assert any(
        e.get("description") == expected_summary and e.get("review_status") == "pending"
        for e in events_body
    )
