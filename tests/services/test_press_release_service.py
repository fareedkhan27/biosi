from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.biosimilar_competitor import BiosimilarCompetitor
from app.services.extraction_service import ExtractedEvent
from app.services.press_release_service import PressReleaseIngestionService

# ---------------------------------------------------------------------------
# Shared test fixture: a realistic ExtractedEvent for scoring tests
# ---------------------------------------------------------------------------

_EXTRACTED_PHASE3 = ExtractedEvent(
    competitor_name="Amgen",
    asset_code="ABP 206",
    molecule_name="nivolumab",
    reference_brand="Opdivo",
    event_type="trial_phase_change",
    event_subtype=None,
    development_stage="Phase 3",
    indication="NSCLC",
    region="North America",
    country="United States",
    event_date="2026-04-01",
    summary="Phase 3 trial initiated for ABP 206.",
    evidence_excerpt="First patient dosed in Phase 3.",
    confidence_score=85,
)


class _TestPressReleaseService(PressReleaseIngestionService):
    async def _get_or_create_source(self):  # type: ignore[override]
        return SimpleNamespace(id=uuid.uuid4())

    async def _resolve_competitor_profile(self, *, competitor_name, asset_code):  # type: ignore[override]
        return None

    async def _get_or_create_competitor(self, competitor_name: str):  # type: ignore[override]
        return SimpleNamespace(id=uuid.uuid4(), name=competitor_name)

    async def _upsert_source_document(self, source, text, source_url, extracted_event):  # type: ignore[override]
        return SimpleNamespace(id=uuid.uuid4(), external_id="press-abc"), True

    async def _upsert_event(self, competitor, competitor_profile, source_document, extracted_event):  # type: ignore[override]
        return SimpleNamespace(id=uuid.uuid4()), True


async def test_press_release_ingestion_uses_extracted_event(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub_extract(text: str, source_url: str | None = None) -> ExtractedEvent:
        return ExtractedEvent(
            competitor_name="amgen",
            asset_code="abp 206",
            molecule_name="nivolumab",
            reference_brand="opdivo",
            event_type="trial update",
            event_subtype="phase advancement",
            development_stage="phase 3",
            indication="nsclc",
            region="europe",
            country="germany",
            event_date="2026-06-15",
            summary="Phase 3 trial initiated.",
            evidence_excerpt="first patient dosed",
            confidence_score=91,
        )

    monkeypatch.setattr("app.services.press_release_service.extract_biosimilar_event_from_text", _stub_extract)

    session = AsyncMock()
    service = _TestPressReleaseService(session=session)

    result = await service.ingest_press_release(
        text="Press release body",
        source_url="https://example.com/release",
    )

    assert result.source_document_created is True
    assert result.event_created is True
    assert result.extracted_event.competitor_name == "Amgen"
    assert result.extracted_event.asset_code == "ABP 206"
    assert result.extracted_event.event_type == "trial_update"
    assert result.extracted_event.country == "Germany"


# ---------------------------------------------------------------------------
# Scoring at ingestion time
# ---------------------------------------------------------------------------


async def test_upsert_event_sets_threat_score_on_new_event() -> None:
    """_upsert_event must compute and set threat_score + traffic_light on a brand-new Event."""
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    service = PressReleaseIngestionService(session=session)
    competitor = SimpleNamespace(id=uuid.uuid4(), name="Amgen")
    source_document = SimpleNamespace(id=uuid.uuid4(), external_id="press-abc123")

    event, was_created = await service._upsert_event(
        competitor=competitor,
        competitor_profile=BiosimilarCompetitor(
            competitor_id=competitor.id,
            name="Amgen",
            tier=1,
            geography="US, EU",
            asset_name="ABP 206",
            stage="Phase 3 complete",
            est_launch_year=2028,
        ),
        source_document=source_document,
        extracted_event=_EXTRACTED_PHASE3,
    )

    assert was_created is True
    added_event = session.add.call_args[0][0]
    assert added_event.threat_score is not None
    assert isinstance(added_event.threat_score, int)
    assert 0 <= added_event.threat_score <= 100
    assert added_event.traffic_light in {"Green", "Amber", "Red"}
    assert added_event.metadata_json["score_breakdown"]["competitor"] == 20


async def test_upsert_event_updates_scoring_on_existing_event() -> None:
    """When _upsert_event finds an existing event it must refresh threat_score and traffic_light."""
    session = AsyncMock()
    existing_event = SimpleNamespace(
        id=uuid.uuid4(),
        threat_score=None,
        traffic_light=None,
        title=None,
        description=None,
        event_date=None,
        metadata_json=None,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=existing_event)
    session.execute = AsyncMock(return_value=execute_result)
    session.flush = AsyncMock()

    service = PressReleaseIngestionService(session=session)
    competitor = SimpleNamespace(id=uuid.uuid4(), name="Amgen")
    source_document = SimpleNamespace(id=uuid.uuid4(), external_id="press-abc123")

    event, was_created = await service._upsert_event(
        competitor=competitor,
        competitor_profile=BiosimilarCompetitor(
            competitor_id=competitor.id,
            name="Amgen",
            tier=1,
            geography="US, EU",
            asset_name="ABP 206",
            stage="Phase 3 complete",
            est_launch_year=2028,
        ),
        source_document=source_document,
        extracted_event=_EXTRACTED_PHASE3,
    )

    assert was_created is False
    assert existing_event.threat_score is not None
    assert isinstance(existing_event.threat_score, int)
    assert existing_event.traffic_light in {"Green", "Amber", "Red"}


def test_phase3_high_confidence_event_scores_amber_or_red() -> None:
    """Phase 3 + confidence 85 + North America should land in Amber or Red range."""
    from app.services.scoring_service import assign_traffic_light, calculate_threat_score

    score = calculate_threat_score(
        event_type="trial_phase_change",
        development_stage="Phase 3",
        confidence_score=85,
        region="North America",
        country="United States",
    )
    light = assign_traffic_light(score)
    assert light in {"Amber", "Red"}, (
        f"Expected Amber/Red for Phase 3 US study, got {light} (score={score})"
    )
