"""Contract-level integration tests for key public /api/v1 endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient

from app.schemas.dashboard import DashboardSummaryResponse
from app.schemas.event import EventRead
from app.schemas.review import ReviewRead
from app.services.clinicaltrials_service import ClinicalTrialsIngestionResult
from app.services.extraction_service import ExtractedEvent
from app.services.press_release_service import PressReleaseIngestionResult

_CT_SERVICE_PATH = (
    "app.services.clinicaltrials_service.ClinicalTrialsIngestionService.ingest_default_terms"
)
_PR_SERVICE_PATH = (
    "app.services.press_release_service.PressReleaseIngestionService.ingest_press_release"
)


@pytest.mark.anyio
async def test_openapi_exposes_key_v1_endpoints_and_tags(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    paths = schema["paths"]

    assert "get" in paths["/api/v1/health"]
    assert "post" in paths["/api/v1/jobs/ingest/clinicaltrials"]
    assert "post" in paths["/api/v1/webhooks/n8n/event"]
    assert "post" in paths["/api/v1/jobs/ingest/press-release"]
    assert "get" in paths["/api/v1/events"]
    assert "post" in paths["/api/v1/events"]
    assert "get" in paths["/api/v1/events/{event_id}"]
    assert "patch" in paths["/api/v1/events/{event_id}"]
    assert "post" in paths["/api/v1/events/{event_id}/approve"]
    assert "post" in paths["/api/v1/events/{event_id}/reject"]
    assert "get" in paths["/api/v1/dashboards/summary"]
    assert "get" in paths["/api/v1/intelligence/weekly-digest-v2"]

    tags = {tag["name"] for tag in schema.get("tags", [])}
    assert {
        "Observability/Health",
        "Jobs",
        "Events",
        "Reviews",
        "Dashboards",
        "Intelligence",
    }.issubset(tags)


@pytest.mark.anyio
async def test_intelligence_weekly_digest_contract(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_build_weekly_digest(session, *, limit: int, approved_only: bool):  # type: ignore[no-untyped-def]
        assert limit == 25
        assert approved_only is True
        return {
            "generated_at": "2026-04-20T12:00:00+00:00",
            "top_insights": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "competitor_id": "22222222-2222-2222-2222-222222222222",
                    "competitor_name": "Amgen",
                    "event_type": "clinical_trial_update",
                    "title": "Phase 3 milestone",
                    "event_date": "2026-04-20",
                    "created_at": "2026-04-20T12:00:00+00:00",
                    "review_status": "approved",
                    "threat_score": 82,
                    "traffic_light": "Red",
                    "development_stage": "Phase 3",
                    "indication": "NSCLC",
                    "country": "United States",
                    "region": "North America",
                    "competitor_tier": 1,
                    "estimated_launch_year": 2028,
                    "score_breakdown": {
                        "stage": 24,
                        "competitor": 20,
                        "geography": 16,
                        "indication": 15,
                        "confidence": 5,
                        "flags": [],
                    },
                    "summary": "Amgen advancing phase 3 in NSCLC (United States) — high likelihood of near-term commercial impact; approaching LOE window (~2028); primary extrapolation anchor",
                    "risk_reason": "Tier 1 competitor in high-priority market aligned with LOE timeline",
                    "recommended_action": "Prepare indication-specific defense plan; monitor regulatory milestones",
                    "confidence_note": "High-confidence source signal.",
                }
            ],
            "competitor_summary": [
                {
                    "competitor_name": "Amgen",
                    "event_count": 1,
                    "max_score": 82,
                    "top_indication": "NSCLC",
                    "summary": "Amgen advancing phase 3 in NSCLC (United States) — high likelihood of near-term commercial impact; approaching LOE window (~2028); primary extrapolation anchor Supported by 1 event in the current digest.",
                }
            ],
            "counts": {"red": 1, "amber": 0, "green": 0},
        }

    monkeypatch.setattr(
        "app.api.v1.intelligence.build_weekly_digest",
        _stub_build_weekly_digest,
    )

    response = await client.get(
        "/api/v1/intelligence/weekly-digest-v2",
        params={"limit": 25, "approved_only": True},
    )
    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {"generated_at", "top_insights", "competitor_summary", "counts"}
    assert body["counts"] == {"red": 1, "amber": 0, "green": 0}
    assert len(body["top_insights"]) == 1
    assert body["top_insights"][0]["risk_reason"] == (
        "Tier 1 competitor in high-priority market aligned with LOE timeline"
    )
    assert body["top_insights"][0]["score_breakdown"]["competitor"] == 20


@pytest.mark.anyio
async def test_openapi_press_release_ingestion_request_and_response_contract(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    operation = schema["paths"]["/api/v1/jobs/ingest/press-release"]["post"]

    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_schema_name = request_ref.rsplit("/", 1)[-1]
    request_schema = schema["components"]["schemas"][request_schema_name]

    assert "text" in request_schema["required"]
    assert "source_url" not in request_schema.get("required", [])
    assert request_schema["additionalProperties"] is False

    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_schema_name = response_ref.rsplit("/", 1)[-1]
    response_schema = schema["components"]["schemas"][response_schema_name]
    assert response_schema["properties"]["source"]["const"] == "press_release"


@pytest.mark.anyio
async def test_health_happy_path_response_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {"status"}
    assert body["status"] == "ok"


@pytest.mark.anyio
async def test_jobs_happy_paths_response_shapes(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_ingest_default_terms(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return ClinicalTrialsIngestionResult(
            search_terms=["nivolumab biosimilar", "ABP 206", "HLX18"],
            studies_seen=3,
            source_documents_created=2,
            source_documents_updated=1,
            events_created=2,
            events_updated=1,
        )

    async def _stub_ingest_press_release(  # type: ignore[no-untyped-def]
        self, text: str, source_url: str | None
    ) -> PressReleaseIngestionResult:
        return PressReleaseIngestionResult(
            extracted_event=ExtractedEvent(
                competitor_name="Amgen",
                asset_code="ABP 206",
                molecule_name="Nivolumab",
                reference_brand="Opdivo",
                event_type="trial_update",
                event_subtype="phase_advancement",
                development_stage="phase_3",
                indication="NSCLC",
                region="North America",
                country="United States",
                event_date="2026-04-01",
                summary="Phase 3 trial initiated.",
                evidence_excerpt="First patient dosed.",
                confidence_score=88,
            ),
            source_document_created=True,
            source_document_updated=False,
            event_created=True,
            event_updated=False,
        )

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub_ingest_default_terms)
    monkeypatch.setattr(_PR_SERVICE_PATH, _stub_ingest_press_release)

    ct = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert ct.status_code == 200
    ct_body = ct.json()
    assert set(ct_body.keys()) == {
        "status",
        "created",
        "updated",
        "skipped",
    }

    pr = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={
            "source_url": "https://example.com/press-release",
            "text": "Biosimilar press release body.",
        },
    )
    assert pr.status_code == 200
    pr_body = pr.json()
    assert set(pr_body.keys()) == {
        "source",
        "source_document_created",
        "source_document_updated",
        "event_created",
        "event_updated",
        "extracted_event",
    }


@pytest.mark.anyio
async def test_events_reviews_and_dashboard_happy_path_flow(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id = str(uuid.uuid4())
    competitor_id = "00000000-0000-0000-0000-000000000001"
    created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    state = {"review_status": "pending", "description": "Milestone announcement", "traffic_light": "Amber"}

    async def _stub_create_event(session, data):  # type: ignore[no-untyped-def]
        return EventRead(
            id=uuid.UUID(event_id),
            competitor_id=uuid.UUID(competitor_id),
            event_type=data.event_type,
            title=data.title,
            description=data.description,
            event_date=date(2026, 4, 1),
            region="North America",
            country="United States",
            traffic_light=state["traffic_light"],
            threat_score=60.0,
            development_stage=None,
            indication=None,
            metadata_json={},
            review_status=state["review_status"],
            created_at=created_at,
        )

    async def _stub_list_events(session, **kwargs):  # type: ignore[no-untyped-def]
        return [
            EventRead(
                id=uuid.UUID(event_id),
                competitor_id=uuid.UUID(competitor_id),
                event_type="launch",
                title="ABP 206 Phase 3 milestone",
                description=state["description"],
                event_date=date(2026, 4, 1),
                region="North America",
                country="United States",
                traffic_light=state["traffic_light"],
                threat_score=60.0,
                development_stage=None,
                indication=None,
                metadata_json={},
                review_status=state["review_status"],
                created_at=created_at,
            )
        ]

    async def _stub_get_event(session, event_id_arg):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        return (
            await _stub_list_events(session)
        )[0]

    async def _stub_update_event(session, event_id_arg, data):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        if data.description is not None:
            state["description"] = data.description
        if data.traffic_light is not None:
            state["traffic_light"] = data.traffic_light
        return (
            await _stub_list_events(session)
        )[0]

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

    async def _stub_reject_event(session, event_id_arg, reviewer_email=None, comment=None):  # type: ignore[no-untyped-def]
        if event_id_arg != event_id:
            return None
        state["review_status"] = "rejected"
        state["traffic_light"] = "Red"
        return ReviewRead(
            id=uuid.uuid4(),
            event_id=uuid.UUID(event_id),
            status="rejected",
            reviewer=reviewer_email,
            review_notes=comment,
            review_status="rejected",
            created_at=created_at,
        )

    async def _stub_get_summary(session):  # type: ignore[no-untyped-def]
        return DashboardSummaryResponse(
            total_events=1,
            approved=0,
            pending=0,
            rejected=1,
            by_traffic_light={"Red": 1},
        )

    monkeypatch.setattr("app.services.event_service.create_event", _stub_create_event)
    monkeypatch.setattr("app.services.event_service.list_events", _stub_list_events)
    monkeypatch.setattr("app.services.event_service.get_event", _stub_get_event)
    monkeypatch.setattr("app.services.event_service.update_event", _stub_update_event)
    monkeypatch.setattr("app.services.review_service.approve_event", _stub_approve_event)
    monkeypatch.setattr("app.services.review_service.reject_event", _stub_reject_event)
    monkeypatch.setattr("app.services.dashboard_service.get_summary", _stub_get_summary)

    create_payload = {
        "competitor_id": competitor_id,
        "event_type": "launch",
        "title": "ABP 206 Phase 3 milestone",
        "description": "Milestone announcement",
        "event_date": "2026-04-01",
        "traffic_light": "Amber",
        "region": "North America",
        "country": "United States",
    }

    created = await client.post("/api/v1/events", json=create_payload)
    assert created.status_code == 201
    created_body = created.json()

    expected_event_keys = {
        "id",
        "competitor_id",
        "event_type",
        "title",
        "description",
        "event_date",
        "region",
        "country",
        "traffic_light",
        "threat_score",
        "development_stage",
        "indication",
        "metadata_json",
        "review_status",
        "created_at",
    }
    assert set(created_body.keys()) == expected_event_keys

    created_event_id = created_body["id"]
    uuid.UUID(created_event_id)
    assert created_event_id == event_id

    listed = await client.get("/api/v1/events")
    assert listed.status_code == 200
    list_body = listed.json()
    assert isinstance(list_body, list)
    assert any(event["id"] == event_id for event in list_body)

    fetched = await client.get(f"/api/v1/events/{event_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == event_id

    patched = await client.patch(
        f"/api/v1/events/{event_id}",
        json={"description": "Updated description", "traffic_light": "Red"},
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Updated description"
    assert patched.json()["traffic_light"] == "Red"

    approved = await client.post(
        f"/api/v1/events/{event_id}/approve",
        json={"reviewer_email": "analyst@biosi.ai", "comment": "Looks valid."},
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["event_id"] == event_id
    assert approved_body["status"] == "approved"

    rejected = await client.post(
        f"/api/v1/events/{event_id}/reject",
        json={"reviewer_email": "analyst@biosi.ai", "comment": "Reclassified."},
    )
    assert rejected.status_code == 200
    rejected_body = rejected.json()
    assert rejected_body["event_id"] == event_id
    assert rejected_body["status"] == "rejected"

    summary = await client.get("/api/v1/dashboards/summary")
    assert summary.status_code == 200
    summary_body = summary.json()
    assert set(summary_body.keys()) == {
        "total_events",
        "approved",
        "pending",
        "rejected",
        "by_traffic_light",
    }
    assert summary_body["total_events"] >= 1
    assert summary_body["rejected"] >= 1
    assert isinstance(summary_body["by_traffic_light"], dict)
    assert "Red" in summary_body["by_traffic_light"]
