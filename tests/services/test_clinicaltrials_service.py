from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.models.biosimilar_competitor import BiosimilarCompetitor
from app.models.competitor import Competitor
from app.services.clinicaltrials_service import ClinicalTrialsIngestionService


def _service() -> ClinicalTrialsIngestionService:
    return ClinicalTrialsIngestionService(
        session=AsyncMock(),
        base_url="https://clinicaltrials.gov/api/v2/studies",
    )


def test_search_terms_include_required_terms() -> None:
    service = _service()
    assert list(service.SEARCH_TERMS) == [
        "nivolumab biosimilar",
        "ABP 206",
        "HLX18",
    ]


def test_parse_date_handles_partial_dates() -> None:
    service = _service()

    assert service._parse_date("2026-04-18") is not None
    assert service._parse_date("2026-04") is not None
    assert service._parse_date("2026") is not None


def test_study_normalization_extracts_key_fields() -> None:
    service = _service()
    study_payload = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT01234567",
                "briefTitle": "ABP 206 in Adults With NSCLC",
            },
            "statusModule": {
                "overallStatus": "RECRUITING",
                "startDateStruct": {"date": "2026-01"},
                "lastUpdatePostDateStruct": {"date": "2026-04-01"},
            },
            "designModule": {"phases": ["PHASE2"]},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Amgen"}},
            "conditionsModule": {"conditions": ["NSCLC"]},
        }
    }

    title = service._study_title(study_payload)
    event_date = service._study_event_date(study_payload)
    metadata = service._study_metadata(study_payload=study_payload, term="ABP 206")

    assert title == "ABP 206 in Adults With NSCLC"
    assert str(event_date) == "2026-01-01"
    assert metadata["nct_id"] == "NCT01234567"
    assert metadata["overall_status"] == "RECRUITING"
    assert metadata["phases"] == ["PHASE2"]


def test_infer_competitor_name_excludes_institutional_sponsors() -> None:
    service = _service()
    study_payload = {
        "protocolSection": {
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Mayo Clinic"},
                "collaborators": [{"name": "National Cancer Institute (NCI)"}],
            }
        }
    }

    assert service._infer_competitor_name(study_payload) is None


def test_infer_competitor_name_keeps_known_sponsor_only() -> None:
    service = _service()
    study_payload = {
        "protocolSection": {
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Shanghai Henlius Biotec, Inc."},
            }
        }
    }

    assert service._infer_competitor_name(study_payload) == "Henlius"


def test_infer_competitor_name_skips_unknown_sponsor() -> None:
    service = _service()
    study_payload = {
        "protocolSection": {
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Independent Cancer Consortium"},
            }
        }
    }

    assert service._infer_competitor_name(study_payload) is None


def test_infer_indication_maps_to_standard_bucket() -> None:
    service = _service()
    study_payload = {
        "protocolSection": {
            "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer"]},
        }
    }

    assert service._infer_indication(study_payload) == "NSCLC"


def test_infer_indication_defaults_to_other_extrapolation() -> None:
    service = _service()
    study_payload = {
        "protocolSection": {
            "conditionsModule": {"conditions": ["Rare Solid Tumor"]},
        }
    }

    assert service._infer_indication(study_payload) == "Other/Extrapolation"


def test_service_requires_v2_endpoint() -> None:
    with pytest.raises(ValidationError):
        ClinicalTrialsIngestionService(
            session=AsyncMock(),
            base_url="https://clinicaltrials.gov/api/query/studies",
        )


# ---------------------------------------------------------------------------
# Scoring at ingestion time
# ---------------------------------------------------------------------------

_PHASE3_STUDY: dict = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT09999999",
            "briefTitle": "ABP 206 Phase 3 in NSCLC",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2026-01"},
        },
        "designModule": {"phases": ["PHASE3"]},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Amgen"}},
        "conditionsModule": {"conditions": ["NSCLC"]},
        "descriptionModule": {"briefSummary": "Phase 3 study of ABP 206."},
        "contactsLocationsModule": {
            "locations": [{"country": "United States"}]
        },
    }
}


def _mock_session(scalar_return_value: object) -> AsyncMock:
    """Return a mock session whose execute().scalar_one_or_none() returns the given value."""
    session = AsyncMock()
    execute_result = MagicMock()  # synchronous result object
    execute_result.scalar_one_or_none = MagicMock(return_value=scalar_return_value)
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


async def test_upsert_event_sets_threat_score_on_new_event() -> None:
    """_upsert_event must set a non-null threat_score and traffic_light on the Event it creates."""
    session = _mock_session(scalar_return_value=None)

    service = _service()
    service.session = session

    competitor = Competitor(id=uuid.uuid4(), name="Amgen")
    source_document = SimpleNamespace(id=uuid.uuid4(), external_id="NCT09999999")
    normalized = service._normalized_event_fields(_PHASE3_STUDY, "ABP 206")

    was_created = await service._upsert_event(
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
        term="ABP 206",
        study_payload=_PHASE3_STUDY,
        normalized_fields=normalized,
    )

    assert was_created is True
    added_event = session.add.call_args[0][0]
    assert added_event.threat_score is not None
    assert isinstance(added_event.threat_score, int)
    assert 0 <= added_event.threat_score <= 100
    assert added_event.traffic_light in {"Green", "Amber", "Red"}
    assert added_event.indication == "NSCLC"
    assert added_event.metadata_json["score_breakdown"]["competitor"] == 20


async def test_upsert_event_updates_scoring_on_existing_event() -> None:
    """When _upsert_event finds an existing event it must refresh threat_score and traffic_light."""
    existing_event = SimpleNamespace(
        id=uuid.uuid4(),
        threat_score=None,
        traffic_light=None,
        title=None,
        description=None,
        event_date=None,
        metadata_json=None,
    )
    session = _mock_session(scalar_return_value=existing_event)

    service = _service()
    service.session = session

    competitor = Competitor(id=uuid.uuid4(), name="Amgen")
    source_document = SimpleNamespace(id=uuid.uuid4(), external_id="NCT09999999")
    normalized = service._normalized_event_fields(_PHASE3_STUDY, "ABP 206")

    was_created = await service._upsert_event(
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
        term="ABP 206",
        study_payload=_PHASE3_STUDY,
        normalized_fields=normalized,
    )

    assert was_created is False
    assert existing_event.threat_score is not None
    assert isinstance(existing_event.threat_score, int)
    assert existing_event.traffic_light in {"Green", "Amber", "Red"}
    assert existing_event.indication == "NSCLC"


def test_phase3_study_produces_high_enough_score_for_amber_or_red() -> None:
    """Phase 3, high-confidence, US-based study should score ≥ 35 (Amber or Red)."""
    service = _service()
    normalized = service._normalized_event_fields(_PHASE3_STUDY, "ABP 206")

    from app.services.scoring_service import assign_traffic_light, calculate_threat_score

    score = calculate_threat_score(
        event_type=service.EVENT_TYPE,
        development_stage=normalized.get("development_stage"),
        confidence_score=normalized.get("confidence_score"),
        region=normalized.get("region"),
        country=normalized.get("country"),
    )
    light = assign_traffic_light(score)
    assert light in {"Amber", "Red"}, f"Expected Amber/Red for Phase 3 US study, got {light} (score={score})"


# ---------------------------------------------------------------------------
# development_stage normalization
# ---------------------------------------------------------------------------


def test_infer_development_stage_returns_canonical_phase3() -> None:
    """PHASE3 API value must normalize to 'Phase 3' so scoring substring match fires."""
    service = _service()
    study = {"protocolSection": {"designModule": {"phases": ["PHASE3"]}}}
    assert service._infer_development_stage(study) == "Phase 3"


def test_infer_development_stage_returns_canonical_phase2() -> None:
    service = _service()
    study = {"protocolSection": {"designModule": {"phases": ["PHASE2"]}}}
    assert service._infer_development_stage(study) == "Phase 2"


def test_infer_development_stage_returns_canonical_phase1() -> None:
    service = _service()
    study = {"protocolSection": {"designModule": {"phases": ["PHASE1"]}}}
    assert service._infer_development_stage(study) == "Phase 1"


def test_infer_development_stage_handles_early_phase1() -> None:
    """ClinicalTrials API v2 also returns 'EARLY_PHASE1' — must map to 'Phase 1'."""
    service = _service()
    study = {"protocolSection": {"designModule": {"phases": ["EARLY_PHASE1"]}}}
    assert service._infer_development_stage(study) == "Phase 1"


def test_development_stage_feeds_scoring_correctly() -> None:
    """Ensure normalized development_stage from ClinicalTrials triggers correct score bonus."""
    from app.services.scoring_service import calculate_threat_score

    service = _service()
    normalized = service._normalized_event_fields(_PHASE3_STUDY, "ABP 206")

    dev_stage = normalized.get("development_stage")
    assert dev_stage == "Phase 3", f"Expected 'Phase 3', got '{dev_stage}'"

    # Isolate stage contribution: no event_type bonus, no geography, no confidence
    score_with_stage = calculate_threat_score(development_stage=dev_stage)
    score_without = calculate_threat_score(development_stage=None)
    assert score_with_stage > score_without, "Phase 3 stage must add points to threat score"
