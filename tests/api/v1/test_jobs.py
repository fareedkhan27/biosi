from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import ExternalServiceError
from app.core.config import settings
from app.services.clinicaltrials_service import ClinicalTrialsIngestionResult
from app.services.extraction_service import ExtractedEvent
from app.services.press_release_service import PressReleaseIngestionResult


@pytest.mark.anyio
async def test_ingest_clinicaltrials_returns_200_and_schema(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_ingest_default_terms(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return ClinicalTrialsIngestionResult(
            search_terms=["nivolumab biosimilar", "ABP 206", "HLX18"],
            studies_seen=12,
            source_documents_created=8,
            source_documents_updated=4,
            events_created=7,
            events_updated=5,
        )

    monkeypatch.setattr(
        "app.services.clinicaltrials_service.ClinicalTrialsIngestionService.ingest_default_terms",
        _stub_ingest_default_terms,
    )
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    response = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {
        "status",
        "created",
        "updated",
        "skipped",
    }
    assert body["status"] == "ok"


@pytest.mark.anyio
async def test_ingest_clinicaltrials_external_service_error_returns_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_ingest_default_terms(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        raise ExternalServiceError("clinicaltrials.gov", "upstream unavailable")

    monkeypatch.setattr(
        "app.services.clinicaltrials_service.ClinicalTrialsIngestionService.ingest_default_terms",
        _stub_ingest_default_terms,
    )
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    response = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert response.status_code == 502

    body = response.json()
    assert "detail" in body
    assert body["detail"]["error"]["type"] == "external_service_error"


@pytest.mark.anyio
async def test_ingest_press_release_returns_200_and_schema(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_ingest_press_release(self, text: str, source_url: str | None):  # type: ignore[no-untyped-def]
        return PressReleaseIngestionResult(
            extracted_event=ExtractedEvent(
                competitor_name="Amgen",
                asset_code="ABP 206",
                molecule_name="Nivolumab",
                reference_brand="Opdivo",
                event_type="trial_update",
                event_subtype="phase_advancement",
                development_stage="phase_3",
                indication="Nsclc",
                region="Europe",
                country="Germany",
                event_date="2026-06-15",
                summary="Phase 3 initiated",
                evidence_excerpt="first patient dosed",
                confidence_score=91,
            ),
            source_document_created=True,
            source_document_updated=False,
            event_created=True,
            event_updated=False,
        )

    monkeypatch.setattr(
        "app.services.press_release_service.PressReleaseIngestionService.ingest_press_release",
        _stub_ingest_press_release,
    )

    response = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={
            "source_url": "https://example.com/press-release",
            "text": "Press release text",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {
        "source",
        "source_document_created",
        "source_document_updated",
        "event_created",
        "event_updated",
        "extracted_event",
    }
    assert body["source"] == "press_release"
    assert body["extracted_event"]["asset_code"] == "ABP 206"


@pytest.mark.anyio
async def test_ingest_press_release_external_service_error_returns_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub_ingest_press_release(self, text: str, source_url: str | None):  # type: ignore[no-untyped-def]
        raise ExternalServiceError("openrouter", "timeout")

    monkeypatch.setattr(
        "app.services.press_release_service.PressReleaseIngestionService.ingest_press_release",
        _stub_ingest_press_release,
    )

    response = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={
            "source_url": "https://example.com/press-release",
            "text": "Press release text",
        },
    )
    assert response.status_code == 502
    body = response.json()
    assert "detail" in body
    assert body["detail"]["error"]["type"] == "external_service_error"
