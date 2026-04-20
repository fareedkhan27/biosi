"""
Contract tests for n8n workflow API compatibility.

Each workflow in docs/n8n-workflows.md specifies which endpoint it calls and
which response fields it reads. These tests verify those fields are present
and correctly typed so the n8n workflows can be configured without surprises.

No real database is needed — the integration conftest provides a mock session.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock
from pydantic import ValidationError as PydanticValidationError

from app.services.clinicaltrials_service import ClinicalTrialsIngestionResult
from app.services.extraction_service import ExtractedEvent
from app.services.press_release_service import PressReleaseIngestionResult
from app.schemas.dashboard import DashboardRecentEventItem


# ---------------------------------------------------------------------------
# Workflow 1: Daily ClinicalTrials ingestion
# POST /api/v1/jobs/ingest/clinicaltrials
# n8n success check: source == "clinicaltrials.gov" AND studies_seen >= 0
# ---------------------------------------------------------------------------

_CT_SERVICE_PATH = (
    "app.services.clinicaltrials_service.ClinicalTrialsIngestionService.ingest_default_terms"
)

N8N_CT_REQUIRED_FIELDS = {"status", "created", "updated", "skipped"}

_PR_SERVICE_PATH = (
    "app.services.press_release_service.PressReleaseIngestionService.ingest_press_release"
)

N8N_PR_REQUIRED_FIELDS = {
    "source",
    "source_document_created",
    "source_document_updated",
    "event_created",
    "event_updated",
    "extracted_event",
}

N8N_PR_EXTRACTED_EVENT_REQUIRED_FIELDS = {
    "competitor_name",
    "asset_code",
    "molecule_name",
    "reference_brand",
    "event_type",
    "event_subtype",
    "development_stage",
    "indication",
    "region",
    "country",
    "event_date",
    "summary",
    "evidence_excerpt",
    "confidence_score",
}


@pytest.mark.anyio
async def test_clinicaltrials_ingestion_response_has_all_n8n_fields(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /ingest/clinicaltrials response must include every field n8n reads."""
    async def _stub(self):  # type: ignore[no-untyped-def]
        return ClinicalTrialsIngestionResult(
            search_terms=["nivolumab biosimilar", "ABP 206", "HLX18"],
            studies_seen=5,
            source_documents_created=3,
            source_documents_updated=2,
            events_created=3,
            events_updated=2,
        )

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    response = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert response.status_code == 200
    body = response.json()
    missing = N8N_CT_REQUIRED_FIELDS - set(body.keys())
    assert not missing, f"n8n Workflow 1 fields missing from response: {missing}"


@pytest.mark.anyio
async def test_clinicaltrials_ingestion_source_field_value(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """n8n IF node checks status === 'ok' for ClinicalTrials runs."""
    async def _stub(self):  # type: ignore[no-untyped-def]
        return ClinicalTrialsIngestionResult(
            search_terms=["ABP 206"],
            studies_seen=1,
            source_documents_created=1,
            source_documents_updated=0,
            events_created=1,
            events_updated=0,
        )

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    response = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_clinicaltrials_ingestion_counters_are_non_negative_ints(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """n8n checks counters >= 0 — all count fields must be non-negative integers."""
    async def _stub(self):  # type: ignore[no-untyped-def]
        return ClinicalTrialsIngestionResult(
            search_terms=["nivolumab biosimilar"],
            studies_seen=0,
            source_documents_created=0,
            source_documents_updated=0,
            events_created=0,
            events_updated=0,
        )

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    for field in ("created", "updated", "skipped"):
        assert isinstance(body[field], int) and body[field] >= 0, (
            f"'{field}' must be non-negative int, got {body[field]!r}"
        )


# ---------------------------------------------------------------------------
# Workflow 4: Press-release ingestion
# POST /api/v1/jobs/ingest/press-release
# n8n reads source + status booleans + extracted_event subfields
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_press_release_ingestion_response_has_all_n8n_fields(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return PressReleaseIngestionResult(
            extracted_event=ExtractedEvent(),
            source_document_created=True,
            source_document_updated=False,
            event_created=True,
            event_updated=False,
        )

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    response = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={"text": "Press release body", "source_url": "https://example.com/pr/1"},
    )
    assert response.status_code == 200
    body = response.json()
    missing = N8N_PR_REQUIRED_FIELDS - set(body.keys())
    assert not missing, f"n8n Workflow 4 fields missing from response: {missing}"

    extracted = body["extracted_event"]
    missing_extracted = N8N_PR_EXTRACTED_EVENT_REQUIRED_FIELDS - set(extracted.keys())
    assert not missing_extracted, (
        "n8n Workflow 4 extracted_event fields missing from response: "
        f"{missing_extracted}"
    )


@pytest.mark.anyio
async def test_press_release_ingestion_source_is_exact_literal(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return PressReleaseIngestionResult(
            extracted_event=ExtractedEvent(confidence_score=70),
            source_document_created=False,
            source_document_updated=True,
            event_created=False,
            event_updated=True,
        )

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (
        await client.post(
            "/api/v1/jobs/ingest/press-release",
            json={"text": "Press release body", "source_url": "https://example.com/pr/2"},
        )
    ).json()
    assert body["source"] == "press_release"


@pytest.mark.anyio
async def test_press_release_ingestion_missing_text_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={"source_url": "https://example.com/pr/3"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Workflow 2 & 3: Recent events (Red alert + Weekly digest)
# GET /api/v1/dashboards/recent-events
# n8n reads: id, competitor_name, event_type, title, created_at,
#            review_status, threat_score, traffic_light
# ---------------------------------------------------------------------------

N8N_RECENT_EVENTS_REQUIRED_FIELDS = {
    "id",
    "competitor_name",
    "event_type",
    "title",
    "created_at",
    "indication",
    "review_status",
    "threat_score",
    "traffic_light",
}


def _mock_recent_events_session(mock_db_session: AsyncMock) -> None:
    """Configure mock_db_session to return one scored, approved Red event row."""
    import uuid
    import datetime

    event = MagicMock()
    event.id = uuid.uuid4()
    event.competitor_id = uuid.uuid4()
    event.event_type = "clinical_trial_update"
    event.title = "ABP 206 Phase 3 milestone"
    event.event_date = datetime.date(2026, 4, 1)
    event.created_at = datetime.datetime(2026, 4, 18, 7, 0, 0,
                                         tzinfo=datetime.timezone.utc)
    event.review_status = "approved"
    event.threat_score = 90
    event.traffic_light = "Red"
    event.indication = "NSCLC"
    event.metadata_json = {"indication": "NSCLC"}

    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[(event, "Amgen")])
    mock_db_session.execute = AsyncMock(return_value=execute_result)


@pytest.mark.anyio
async def test_recent_events_response_has_all_n8n_fields(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """GET /dashboards/recent-events items must include every field n8n Workflow 2/3 reads."""
    _mock_recent_events_session(mock_db_session)
    response = await client.get("/api/v1/dashboards/recent-events")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list) and items, "Expected at least one item in response"

    item = items[0]
    missing = N8N_RECENT_EVENTS_REQUIRED_FIELDS - set(item.keys())
    assert not missing, f"n8n Workflow 2/3 fields missing from recent-events item: {missing}"


@pytest.mark.anyio
async def test_recent_events_created_at_is_iso_string(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """n8n filters by created_at >= now - 24h; field must be ISO 8601 string parseable by JS Date()."""
    _mock_recent_events_session(mock_db_session)
    items = (await client.get("/api/v1/dashboards/recent-events")).json()
    created_at = items[0]["created_at"]
    assert isinstance(created_at, str), f"created_at must be a string, got {type(created_at)}"
    # Must be parseable as ISO 8601 — datetime.fromisoformat covers all valid formats
    from datetime import datetime
    parsed = datetime.fromisoformat(created_at)
    assert parsed is not None


@pytest.mark.anyio
async def test_recent_events_review_status_is_valid_string(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """n8n filters review_status === 'approved'; must be string from known set."""
    _mock_recent_events_session(mock_db_session)
    items = (await client.get("/api/v1/dashboards/recent-events")).json()
    review_status = items[0]["review_status"]
    assert isinstance(review_status, str)
    assert review_status in {"approved", "pending", "rejected"}, (
        f"review_status must be one of approved/pending/rejected, got {review_status!r}"
    )


@pytest.mark.anyio
async def test_recent_events_traffic_light_is_valid_string(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """n8n filters traffic_light === 'Red'; must be string from known set."""
    _mock_recent_events_session(mock_db_session)
    items = (await client.get("/api/v1/dashboards/recent-events")).json()
    traffic_light = items[0]["traffic_light"]
    assert isinstance(traffic_light, str)
    assert traffic_light in {"Green", "Amber", "Red"}, (
        f"traffic_light must be Green/Amber/Red, got {traffic_light!r}"
    )


@pytest.mark.anyio
async def test_recent_events_threat_score_is_int_in_range(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """n8n reads threat_score for digest grouping; when present must be int in [0, 100]."""
    _mock_recent_events_session(mock_db_session)
    items = (await client.get("/api/v1/dashboards/recent-events")).json()
    threat_score = items[0]["threat_score"]
    # threat_score is nullable — null is valid for unscored events.
    if threat_score is not None:
        assert isinstance(threat_score, int), f"threat_score must be int, got {type(threat_score)}"
        assert 0 <= threat_score <= 100, f"threat_score out of range: {threat_score}"


@pytest.mark.anyio
async def test_recent_events_competitor_name_is_string_or_null(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """n8n uses competitor_name in notification body; must be str or null."""
    _mock_recent_events_session(mock_db_session)
    items = (await client.get("/api/v1/dashboards/recent-events")).json()
    competitor_name = items[0]["competitor_name"]
    assert competitor_name is None or isinstance(competitor_name, str)


# ---------------------------------------------------------------------------
# Task A — Enum / Literal constraints (schema-level enforcement)
# ---------------------------------------------------------------------------


def _make_base_item_dict(**overrides: object) -> dict:
    """Return a minimal valid DashboardRecentEventItem payload."""
    import datetime
    base: dict = {
        "id": "00000000-0000-0000-0000-000000000001",
        "competitor_id": "00000000-0000-0000-0000-000000000002",
        "competitor_name": "Amgen",
        "event_type": "clinical_trial_update",
        "title": "ABP 206 Phase 3",
        "event_date": None,
        "created_at": datetime.datetime(2026, 4, 18, 7, 0, 0,
                                        tzinfo=datetime.timezone.utc).isoformat(),
        "indication": "NSCLC",
        "review_status": "approved",
        "threat_score": 90,
        "traffic_light": "Red",
    }
    base.update(overrides)
    return base


def test_dashboard_item_review_status_rejects_invalid_value() -> None:
    """Pydantic must reject review_status values not in {approved, pending, rejected}."""
    with pytest.raises(PydanticValidationError):
        DashboardRecentEventItem(**_make_base_item_dict(review_status="UNKNOWN"))


def test_dashboard_item_review_status_accepts_all_valid_values() -> None:
    """Pydantic must accept all three canonical review_status values."""
    for status in ("approved", "pending", "rejected"):
        item = DashboardRecentEventItem(**_make_base_item_dict(review_status=status))
        assert item.review_status == status


def test_dashboard_item_traffic_light_rejects_invalid_value() -> None:
    """Pydantic must reject traffic_light values not in {Green, Amber, Red}."""
    with pytest.raises(PydanticValidationError):
        DashboardRecentEventItem(**_make_base_item_dict(traffic_light="yellow"))


def test_dashboard_item_traffic_light_rejects_wrong_case() -> None:
    """traffic_light must be title-case; 'red' (lowercase) must be rejected."""
    with pytest.raises(PydanticValidationError):
        DashboardRecentEventItem(**_make_base_item_dict(traffic_light="red"))


def test_dashboard_item_traffic_light_accepts_all_valid_values() -> None:
    """Pydantic must accept Green, Amber, and Red exactly."""
    for light in ("Green", "Amber", "Red"):
        item = DashboardRecentEventItem(**_make_base_item_dict(traffic_light=light))
        assert item.traffic_light == light


def test_dashboard_item_traffic_light_accepts_null() -> None:
    """traffic_light may be null for unscored events."""
    item = DashboardRecentEventItem(**_make_base_item_dict(traffic_light=None))
    assert item.traffic_light is None


# ---------------------------------------------------------------------------
# Task B — Date filtering via since_hours / since_days
# ---------------------------------------------------------------------------


def _mock_empty_session(mock_db_session: AsyncMock) -> None:
    """Configure mock to return an empty result (endpoint just needs to not crash)."""
    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[])
    mock_db_session.execute = AsyncMock(return_value=execute_result)


@pytest.mark.anyio
async def test_recent_events_since_hours_param_accepted(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """GET /dashboards/recent-events?since_hours=24 must return 200 without error."""
    _mock_empty_session(mock_db_session)
    response = await client.get("/api/v1/dashboards/recent-events?since_hours=24")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_recent_events_since_days_param_accepted(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """GET /dashboards/recent-events?since_days=7 must return 200 without error."""
    _mock_empty_session(mock_db_session)
    response = await client.get("/api/v1/dashboards/recent-events?since_days=7")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_recent_events_limit_still_works_without_date_filter(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """Backward compat: ?limit=10 with no since_* param must still return 200."""
    _mock_empty_session(mock_db_session)
    response = await client.get("/api/v1/dashboards/recent-events?limit=10")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Task C — Unscored (threat_score=None) events must be visible in recent-events
# ---------------------------------------------------------------------------


def _mock_unscored_approved_event_session(mock_db_session: AsyncMock) -> None:
    """Return one approved event with threat_score=None and traffic_light=None."""
    import uuid
    import datetime

    event = MagicMock()
    event.id = uuid.uuid4()
    event.competitor_id = uuid.uuid4()
    event.event_type = "regulatory_filing"
    event.title = "BLA submitted for HLX18"
    event.event_date = None
    event.created_at = datetime.datetime(2026, 4, 18, 8, 0, 0,
                                          tzinfo=datetime.timezone.utc)
    event.review_status = "approved"
    event.threat_score = None   # not yet scored
    event.traffic_light = None  # not yet scored

    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[(event, "Henlius")])
    mock_db_session.execute = AsyncMock(return_value=execute_result)


@pytest.mark.anyio
async def test_recent_events_includes_unscored_approved_events(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """
    An approved event with threat_score=None must NOT be silently excluded.

    This was the Task C bug: get_recent_events formerly filtered
    WHERE threat_score IS NOT NULL, hiding approved-but-unscored events from n8n.
    """
    _mock_unscored_approved_event_session(mock_db_session)
    response = await client.get("/api/v1/dashboards/recent-events")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1, (
        "Unscored approved event must appear in recent-events (threat_score IS NOT NULL "
        "filter must not be applied here)"
    )
    assert items[0]["threat_score"] is None
    assert items[0]["traffic_light"] is None
    assert items[0]["review_status"] == "approved"


def _mock_recent_events_malformed_status_session(
    mock_db_session: AsyncMock,
    *,
    review_status: str,
    traffic_light: str | None,
) -> None:
    """Return one row with intentionally malformed status/light strings."""
    import uuid
    import datetime

    event = MagicMock()
    event.id = uuid.uuid4()
    event.competitor_id = uuid.uuid4()
    event.event_type = "clinical_trial_update"
    event.title = "Malformed status payload"
    event.event_date = datetime.date(2026, 4, 1)
    event.created_at = datetime.datetime(2026, 4, 19, 7, 0, 0, tzinfo=datetime.timezone.utc)
    event.review_status = review_status
    event.threat_score = 55
    event.traffic_light = traffic_light

    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[(event, "Amgen")])
    mock_db_session.execute = AsyncMock(return_value=execute_result)


@pytest.mark.anyio
async def test_recent_events_normalizes_quoted_review_status_and_traffic_light(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """Quoted DB values like "'pending'" must be normalized so response model validation succeeds."""
    _mock_recent_events_malformed_status_session(
        mock_db_session,
        review_status="'pending'",
        traffic_light="'red'",
    )

    response = await client.get("/api/v1/dashboards/recent-events")
    assert response.status_code == 200

    items = response.json()
    assert len(items) == 1
    assert items[0]["review_status"] == "pending"
    assert items[0]["traffic_light"] == "Red"


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["approved", "pending", "rejected"])
async def test_recent_events_serializes_all_valid_review_statuses(
    client: AsyncClient,
    mock_db_session: AsyncMock,
    status: str,
) -> None:
    """recent-events must serialize approved/pending/rejected values exactly."""
    _mock_recent_events_malformed_status_session(
        mock_db_session,
        review_status=status,
        traffic_light="Amber",
    )

    response = await client.get("/api/v1/dashboards/recent-events")
    assert response.status_code == 200

    items = response.json()
    assert len(items) == 1
    assert items[0]["review_status"] == status
