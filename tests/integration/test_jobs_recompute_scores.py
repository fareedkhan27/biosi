"""Integration tests for POST /api/v1/jobs/recompute-scores."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_recompute_scores_returns_ok_schema(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    """The recompute endpoint must return the expected response shape."""
    event = MagicMock()
    event.id = uuid.uuid4()
    event.event_type = "clinical_trial_update"
    event.threat_score = 55
    event.traffic_light = "Amber"
    event.metadata_json = {
        "development_stage": "Phase 2",
        "country": "India",
        "confidence_score": 70,
    }

    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = [event]
    mock_db_session.execute = AsyncMock(return_value=execute_result)

    response = await client.post("/api/v1/jobs/recompute-scores")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["events_processed"] == 1
    assert isinstance(body["events_updated"], int)
    assert isinstance(body["events_skipped"], int)
    assert "avg_threat_score_before" in body
    assert "avg_threat_score_after" in body
