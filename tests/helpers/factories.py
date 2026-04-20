"""
In-memory factory helpers for building test data payloads and result stubs.

These factories never touch the database; they produce plain Python objects
suitable for monkeypatching service return values or seeding JSON payloads.
"""

from __future__ import annotations

from app.services.clinicaltrials_service import ClinicalTrialsIngestionResult
from app.services.extraction_service import ExtractedEvent
from app.services.press_release_service import PressReleaseIngestionResult


# ---------------------------------------------------------------------------
# ExtractedEvent helpers
# ---------------------------------------------------------------------------

def make_extracted_event(
    *,
    competitor_name: str | None = "Amgen",
    asset_code: str | None = "ABP 206",
    molecule_name: str | None = "Nivolumab",
    reference_brand: str | None = "Opdivo",
    event_type: str | None = "trial_update",
    event_subtype: str | None = "phase_advancement",
    development_stage: str | None = "phase_3",
    indication: str | None = "NSCLC",
    region: str | None = "North America",
    country: str | None = "United States",
    event_date: str | None = "2026-04-01",
    summary: str | None = "Phase 3 trial of ABP 206 (nivolumab biosimilar) initiated.",
    evidence_excerpt: str | None = "First patient dosed in pivotal Phase 3 study.",
    confidence_score: int | None = 88,
) -> ExtractedEvent:
    return ExtractedEvent(
        competitor_name=competitor_name,
        asset_code=asset_code,
        molecule_name=molecule_name,
        reference_brand=reference_brand,
        event_type=event_type,
        event_subtype=event_subtype,
        development_stage=development_stage,
        indication=indication,
        region=region,
        country=country,
        event_date=event_date,
        summary=summary,
        evidence_excerpt=evidence_excerpt,
        confidence_score=confidence_score,
    )


# ---------------------------------------------------------------------------
# ClinicalTrials ingestion result helpers
# ---------------------------------------------------------------------------

def make_ct_ingestion_result(
    *,
    search_terms: list[str] | None = None,
    studies_seen: int = 5,
    source_documents_created: int = 3,
    source_documents_updated: int = 2,
    events_created: int = 3,
    events_updated: int = 2,
) -> ClinicalTrialsIngestionResult:
    return ClinicalTrialsIngestionResult(
        search_terms=search_terms or ["nivolumab biosimilar", "ABP 206", "HLX18"],
        studies_seen=studies_seen,
        source_documents_created=source_documents_created,
        source_documents_updated=source_documents_updated,
        events_created=events_created,
        events_updated=events_updated,
    )


def make_ct_ingestion_result_zero_created(
    *,
    search_terms: list[str] | None = None,
    studies_seen: int = 5,
) -> ClinicalTrialsIngestionResult:
    """Simulates a second run of the same data (all records already exist)."""
    return ClinicalTrialsIngestionResult(
        search_terms=search_terms or ["nivolumab biosimilar", "ABP 206", "HLX18"],
        studies_seen=studies_seen,
        source_documents_created=0,
        source_documents_updated=studies_seen,
        events_created=0,
        events_updated=studies_seen,
    )


# ---------------------------------------------------------------------------
# Press release ingestion result helpers
# ---------------------------------------------------------------------------

def make_pr_ingestion_result(
    *,
    extracted_event: ExtractedEvent | None = None,
    source_document_created: bool = True,
    source_document_updated: bool = False,
    event_created: bool = True,
    event_updated: bool = False,
) -> PressReleaseIngestionResult:
    return PressReleaseIngestionResult(
        extracted_event=extracted_event or make_extracted_event(),
        source_document_created=source_document_created,
        source_document_updated=source_document_updated,
        event_created=event_created,
        event_updated=event_updated,
    )


def make_pr_ingestion_result_updated(
    *,
    extracted_event: ExtractedEvent | None = None,
) -> PressReleaseIngestionResult:
    """Simulates a second ingest of the same URL (existing records updated)."""
    return PressReleaseIngestionResult(
        extracted_event=extracted_event or make_extracted_event(),
        source_document_created=False,
        source_document_updated=True,
        event_created=False,
        event_updated=True,
    )


# ---------------------------------------------------------------------------
# Sample ClinicalTrials API study payload
# ---------------------------------------------------------------------------

SAMPLE_CT_STUDY: dict = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT98765432",
            "briefTitle": "ABP 206 Phase 3 Efficacy vs Opdivo",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2026-01-15"},
            "lastUpdatePostDateStruct": {"date": "2026-04-01"},
        },
        "designModule": {"phases": ["PHASE3"]},
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "Amgen"},
        },
        "conditionsModule": {"conditions": ["Non-small cell lung cancer"]},
        "descriptionModule": {
            "briefSummary": "A pivotal Phase 3 study comparing ABP 206 to Opdivo."
        },
        "contactsLocationsModule": {
            "locations": [{"country": "United States"}]
        },
    }
}

SAMPLE_CT_API_RESPONSE: dict = {
    "studies": [SAMPLE_CT_STUDY],
    "totalCount": 1,
}
