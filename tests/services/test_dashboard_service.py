from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import dashboard_service


def _make_event(
    *,
    review_status: str = "approved",
    threat_score: int | None = 72,
    traffic_light: str | None = "Red",
    indication: str | None = "NSCLC",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        competitor_id=uuid.uuid4(),
        event_type="clinical_trial_update",
        title="Test Event",
        event_date=None,
        created_at=__import__("datetime").datetime(2026, 4, 18, tzinfo=__import__("datetime").timezone.utc),
        review_status=review_status,
        threat_score=threat_score,
        traffic_light=traffic_light,
        indication=indication,
        metadata_json={"indication": indication, "country": "United States"}
        if indication is not None
        else {"country": "United States"},
    )


def _mock_session_returning(rows: list[tuple]) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar_one = MagicMock(return_value=0)
    session.execute = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# top-threats: approved_only=True (default)
# ---------------------------------------------------------------------------


async def test_get_top_threats_approved_only_excludes_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """With approved_only=True, only approved events must reach the caller."""
    approved = _make_event(review_status="approved", threat_score=80)
    pending = _make_event(review_status="pending", threat_score=75)

    returned_rows: list[tuple] = []

    async def _fake_execute(stmt):
        # Simulate DB honouring WHERE review_status = 'approved'
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "'approved'" in compiled, "Query must filter to approved events"
        result = MagicMock()
        result.all = MagicMock(return_value=[(approved, "Amgen")])
        return result

    session = AsyncMock()
    session.execute = _fake_execute

    items = await dashboard_service.get_top_threats(session, approved_only=True)
    assert all(item["review_status"] == "approved" for item in items)


async def test_get_top_threats_approved_only_false_includes_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """With approved_only=False, pending events (non-rejected) must be included."""
    pending = _make_event(review_status="pending", threat_score=65)

    async def _fake_execute(stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "'rejected'" in compiled, "Query must exclude rejected but not pending"
        result = MagicMock()
        result.all = MagicMock(return_value=[(pending, "Henlius")])
        return result

    session = AsyncMock()
    session.execute = _fake_execute

    items = await dashboard_service.get_top_threats(session, approved_only=False)
    assert items[0]["review_status"] == "pending"


async def test_get_top_threats_requires_non_null_threat_score() -> None:
    """top-threats query must include WHERE threat_score IS NOT NULL."""
    session = AsyncMock()
    captured: list[str] = []

    async def _capture_execute(stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        captured.append(compiled)
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        return result

    session.execute = _capture_execute

    await dashboard_service.get_top_threats(session, approved_only=True)
    assert captured, "execute must have been called"
    assert "threat_score IS NOT NULL" in captured[0], (
        f"Expected 'threat_score IS NOT NULL' in query; got:\n{captured[0]}"
    )


async def test_get_top_threats_excludes_institution_like_competitor_names() -> None:
    session = AsyncMock()
    captured: list[str] = []

    async def _capture_execute(stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        captured.append(compiled)
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        return result

    session.execute = _capture_execute

    await dashboard_service.get_top_threats(session, approved_only=False)
    assert captured
    query = captured[0].lower()
    assert "not like" in query
    assert "university" in query
    assert "hospital" in query


async def test_get_top_threats_includes_indication() -> None:
    event = _make_event(indication="RCC")
    session = _mock_session_returning([(event, "Amgen", "United States")])

    items = await dashboard_service.get_top_threats(session, approved_only=False)
    assert items[0]["indication"] == "RCC"


# ---------------------------------------------------------------------------
# recent-events: include scored and unscored events
# ---------------------------------------------------------------------------


async def test_get_recent_events_does_not_require_non_null_threat_score() -> None:
    """recent-events should not enforce threat_score IS NOT NULL."""
    session = AsyncMock()
    captured: list[str] = []

    async def _capture_execute(stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        captured.append(compiled)
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        return result

    session.execute = _capture_execute

    await dashboard_service.get_recent_events(session)
    assert captured
    assert "threat_score IS NOT NULL" not in captured[0], (
        f"Did not expect 'threat_score IS NOT NULL' in recent-events query; got:\n{captured[0]}"
    )


async def test_get_recent_events_excludes_rejected_by_default() -> None:
    """recent-events must not show rejected events by default."""
    session = AsyncMock()
    captured: list[str] = []

    async def _capture_execute(stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        captured.append(compiled)
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        return result

    session.execute = _capture_execute

    await dashboard_service.get_recent_events(session)
    assert captured
    assert "'rejected'" in captured[0], "Query must exclude rejected events"


async def test_get_recent_events_includes_indication() -> None:
    event = _make_event(indication="Melanoma")
    session = _mock_session_returning([(event, "Amgen", "United States")])

    items = await dashboard_service.get_recent_events(session)
    assert items[0]["indication"] == "Melanoma"
    assert items[0]["country"] == "United States"


async def test_get_top_threats_dedupes_repeated_competitor() -> None:
    high = _make_event(threat_score=82)
    lower = _make_event(threat_score=61)
    session = _mock_session_returning(
        [
            (high, "Amgen", "United States"),
            (lower, "Amgen", "United States"),
        ]
    )

    items = await dashboard_service.get_top_threats(session, approved_only=False)
    assert len(items) == 1
    assert items[0]["threat_score"] == 82


# ---------------------------------------------------------------------------
# review-queue: pending only
# ---------------------------------------------------------------------------


async def test_get_review_queue_shows_only_pending() -> None:
    """review-queue must show only pending events."""
    session = AsyncMock()
    captured: list[str] = []

    async def _capture_execute(stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        captured.append(compiled)
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        return result

    session.execute = _capture_execute

    await dashboard_service.get_review_queue(session)
    assert captured
    assert "'pending'" in captured[0], "review-queue must filter to pending events"


async def test_get_review_queue_excludes_institution_like_competitor_names() -> None:
    session = AsyncMock()
    captured: list[str] = []

    async def _capture_execute(stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        captured.append(compiled)
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        return result

    session.execute = _capture_execute

    await dashboard_service.get_review_queue(session)
    assert captured
    query = captured[0].lower()
    assert "not like" in query
    assert "institute" in query
