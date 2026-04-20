from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.biosimilar_competitor import BiosimilarCompetitor
from app.services.event_service import _to_event_read


def _make_event(**overrides) -> SimpleNamespace:
    defaults = dict(
        id=uuid.uuid4(),
        competitor_id=uuid.uuid4(),
        event_type="trial_phase_change",
        title="ABP 206 Phase 3",
        description=None,
        event_date=None,
        threat_score=55,
        traffic_light="Amber",
        review_status="pending",
        metadata_json={"region": "North America", "country": "United States"},
        created_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# _to_event_read
# ---------------------------------------------------------------------------


def test_to_event_read_exposes_review_status() -> None:
    event = _make_event(review_status="pending")
    result = _to_event_read(event)
    assert result.review_status == "pending"


def test_to_event_read_propagates_approved_status() -> None:
    event = _make_event(review_status="approved")
    result = _to_event_read(event)
    assert result.review_status == "approved"


def test_to_event_read_propagates_rejected_status() -> None:
    event = _make_event(review_status="rejected")
    result = _to_event_read(event)
    assert result.review_status == "rejected"


def test_to_event_read_maps_scoring_fields() -> None:
    event = _make_event(threat_score=72, traffic_light="Red")
    result = _to_event_read(event)
    assert result.threat_score == 72.0
    assert result.traffic_light == "Red"


# ---------------------------------------------------------------------------
# Ingestion default: new events from upsert must carry review_status="pending"
# ---------------------------------------------------------------------------


async def test_clinicaltrials_upsert_new_event_sets_pending() -> None:
    """Event created by _upsert_event in ClinicalTrials service must default to pending."""
    import uuid as _uuid
    from unittest.mock import AsyncMock
    from app.services.clinicaltrials_service import ClinicalTrialsIngestionService
    from app.models.competitor import Competitor

    _STUDY: dict = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test Study"},
            "statusModule": {"overallStatus": "RECRUITING", "startDateStruct": {"date": "2026-01"}},
            "designModule": {"phases": ["PHASE3"]},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Amgen"}},
            "conditionsModule": {"conditions": ["NSCLC"]},
            "descriptionModule": {"briefSummary": "Test."},
            "contactsLocationsModule": {"locations": [{"country": "United States"}]},
        }
    }

    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    service = ClinicalTrialsIngestionService(
        session=session,
        base_url="https://clinicaltrials.gov/api/v2/studies",
    )
    competitor = Competitor(id=_uuid.uuid4(), name="Amgen")
    source_doc = SimpleNamespace(id=_uuid.uuid4(), external_id="NCT00000001")
    normalized = service._normalized_event_fields(_STUDY, "ABP 206")

    await service._upsert_event(
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
        source_document=source_doc,
        term="ABP 206",
        study_payload=_STUDY,
        normalized_fields=normalized,
    )

    added_event = session.add.call_args[0][0]
    assert added_event.review_status == "pending"


async def test_press_release_upsert_new_event_sets_pending() -> None:
    """Event created by _upsert_event in PressRelease service must default to pending."""
    import uuid as _uuid
    from unittest.mock import AsyncMock
    from app.services.press_release_service import PressReleaseIngestionService
    from app.services.extraction_service import ExtractedEvent

    extracted = ExtractedEvent(
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
        evidence_excerpt="First patient dosed.",
        confidence_score=85,
    )

    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    service = PressReleaseIngestionService(session=session)
    competitor = SimpleNamespace(id=_uuid.uuid4(), name="Amgen")
    source_doc = SimpleNamespace(id=_uuid.uuid4(), external_id="press-abc")

    await service._upsert_event(
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
        source_document=source_doc,
        extracted_event=extracted,
    )

    added_event = session.add.call_args[0][0]
    assert added_event.review_status == "pending"
