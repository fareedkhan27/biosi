"""Integration tests for POST /api/v1/intelligence/generate-briefings."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


N8N_BRIEFING_REQUIRED_FIELDS = {
    "department",
    "generated_at",
    "executive_summary",
    "market_sections",
    "event_cards",
    "milestones",
}


def _mock_briefing_session(mock_db_session: AsyncMock) -> None:
    """Return one Red and one Amber event for briefing generation."""
    import uuid
    import datetime

    red_event = MagicMock()
    red_event.id = uuid.uuid4()
    red_event.competitor_id = uuid.uuid4()
    red_event.event_type = "clinical_trial_update"
    red_event.title = "Amgen ABP 206 Phase 3"
    red_event.event_date = datetime.date(2026, 6, 1)
    red_event.created_at = datetime.datetime(2026, 4, 20, 7, 0, 0, tzinfo=datetime.timezone.utc)
    red_event.review_status = "approved"
    red_event.threat_score = 90
    red_event.traffic_light = "Red"
    red_event.metadata_json = {
        "development_stage": "Phase 3",
        "indication": "NSCLC",
        "country": "United States",
        "competitor_tier": 1,
        "score_breakdown": {
            "stage": 24,
            "competitor": 20,
            "geography": 16,
            "indication": 15,
            "confidence": 5,
            "flags": [],
        },
    }

    amber_event = MagicMock()
    amber_event.id = uuid.uuid4()
    amber_event.competitor_id = uuid.uuid4()
    amber_event.event_type = "press_release_update"
    amber_event.title = "Henlius HLX18 regulatory update"
    amber_event.event_date = datetime.date(2026, 5, 15)
    amber_event.created_at = datetime.datetime(2026, 4, 18, 7, 0, 0, tzinfo=datetime.timezone.utc)
    amber_event.review_status = "approved"
    amber_event.threat_score = 62
    amber_event.traffic_light = "Amber"
    amber_event.metadata_json = {
        "development_stage": "Phase 2",
        "indication": "RCC",
        "country": "China",
        "competitor_tier": 2,
        "score_breakdown": {
            "stage": 16,
            "competitor": 15,
            "geography": 10,
            "indication": 10,
            "confidence": 4,
            "flags": [],
        },
    }

    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[
        (red_event, "Amgen"),
        (amber_event, "Henlius"),
    ])
    mock_db_session.execute = AsyncMock(return_value=execute_result)


@pytest.mark.anyio
@pytest.mark.parametrize("department", ["regulatory", "commercial", "medical_affairs", "market_access"])
async def test_generate_briefings_returns_schema_for_all_departments(
    client: AsyncClient,
    mock_db_session: AsyncMock,
    department: str,
) -> None:
    """Every valid department must return a complete briefing payload."""
    _mock_briefing_session(mock_db_session)
    response = await client.post(
        "/api/v1/intelligence/generate-briefings",
        params={"department": department},
    )
    assert response.status_code == 200

    body = response.json()
    missing = N8N_BRIEFING_REQUIRED_FIELDS - set(body.keys())
    assert not missing, f"Briefing fields missing for {department}: {missing}"

    assert body["department"] == department
    assert isinstance(body["executive_summary"], str)
    assert isinstance(body["market_sections"], list)
    assert isinstance(body["event_cards"], list)
    assert len(body["event_cards"]) == 2
    assert isinstance(body["milestones"], list)

    # Each event card must have a department-specific frame
    for card in body["event_cards"]:
        assert "department_frame" in card
        assert isinstance(card["department_frame"], str)


@pytest.mark.anyio
async def test_generate_briefings_rejects_invalid_department(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """An unknown department must return 400."""
    mock_db_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    response = await client.post(
        "/api/v1/intelligence/generate-briefings",
        params={"department": "invalid_department"},
    )
    assert response.status_code == 400
