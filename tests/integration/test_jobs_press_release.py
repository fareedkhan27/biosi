"""
Integration tests for POST /api/v1/jobs/ingest/press-release.

Exercises:
- 200 success path with mocked extraction service
- full response schema (source, booleans, extracted_event sub-object)
- extracted_event fields present and correctly typed
- 422 validation error on missing/malformed body
- duplicate/idempotent ingest: second run updates rather than creates
- ExternalServiceError → 502 with structured error payload
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import ExternalServiceError, ValidationError
from app.services.press_release_service import PressReleaseIngestionResult
from tests.helpers.factories import (
    make_extracted_event,
    make_pr_ingestion_result,
    make_pr_ingestion_result_updated,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PR_SERVICE_PATH = (
    "app.services.press_release_service.PressReleaseIngestionService.ingest_press_release"
)

_VALID_PAYLOAD = {
    "source_url": "https://example.com/press-release/hlx18-phase3",
    "text": (
        "Henlius announced FDA IND clearance for HLX18, a biosimilar candidate "
        "to nivolumab (Opdivo), initiating a Phase 3 study in NSCLC patients."
    ),
}

_EXPECTED_TOP_LEVEL_KEYS = {
    "source",
    "source_document_created",
    "source_document_updated",
    "event_created",
    "event_updated",
    "extracted_event",
}

_EXPECTED_EXTRACTED_EVENT_KEYS = {
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


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_press_release_returns_200(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    response = await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_ingest_press_release_response_has_all_required_top_level_keys(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    assert set(body.keys()) == _EXPECTED_TOP_LEVEL_KEYS


@pytest.mark.anyio
async def test_ingest_press_release_source_is_press_release(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    assert body["source"] == "press_release"


@pytest.mark.anyio
async def test_ingest_press_release_boolean_flags_are_booleans(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    for key in ("source_document_created", "source_document_updated", "event_created", "event_updated"):
        assert isinstance(body[key], bool), f"expected bool for {key}"


@pytest.mark.anyio
async def test_ingest_press_release_extracted_event_has_all_keys(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    assert _EXPECTED_EXTRACTED_EVENT_KEYS.issubset(set(body["extracted_event"].keys()))


@pytest.mark.anyio
async def test_ingest_press_release_extracted_event_values(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = make_extracted_event(
        competitor_name="Henlius",
        asset_code="HLX18",
        molecule_name="Nivolumab",
        reference_brand="Opdivo",
        event_type="regulatory_approval",
        development_stage="phase_3",
        confidence_score=91,
    )

    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result(extracted_event=event)

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    ee = body["extracted_event"]
    assert ee["competitor_name"] == "Henlius"
    assert ee["asset_code"] == "HLX18"
    assert ee["molecule_name"] == "Nivolumab"
    assert ee["reference_brand"] == "Opdivo"
    assert ee["event_type"] == "regulatory_approval"
    assert ee["development_stage"] == "phase_3"
    assert ee["confidence_score"] == 91


@pytest.mark.anyio
async def test_ingest_press_release_confidence_score_is_int_or_null(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result(extracted_event=make_extracted_event(confidence_score=75))

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    score = body["extracted_event"]["confidence_score"]
    assert score is None or isinstance(score, int)


@pytest.mark.anyio
async def test_ingest_press_release_created_flags_true_on_first_ingest(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result(source_document_created=True, event_created=True)

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    assert body["source_document_created"] is True
    assert body["event_created"] is True
    assert body["source_document_updated"] is False
    assert body["event_updated"] is False


# ---------------------------------------------------------------------------
# Validation error / missing body
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_press_release_missing_body_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/jobs/ingest/press-release")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_ingest_press_release_missing_text_field_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={"source_url": "https://example.com/pr"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_ingest_press_release_422_has_detail_list(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/jobs/ingest/press-release")
    body = response.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)
    assert len(body["detail"]) > 0


@pytest.mark.anyio
async def test_ingest_press_release_source_url_is_optional(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """source_url is optional; omitting it should still return 200."""

    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    response = await client.post(
        "/api/v1/jobs/ingest/press-release",
        json={"text": "Some press release text about biosimilar."},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Duplicate / idempotent path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_press_release_second_run_updates_existing_records(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_pr_ingestion_result()
        return make_pr_ingestion_result_updated()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    r1 = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    r2 = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()

    assert r1["source_document_created"] is True
    assert r1["event_created"] is True

    assert r2["source_document_created"] is False
    assert r2["source_document_updated"] is True
    assert r2["event_created"] is False
    assert r2["event_updated"] is True


@pytest.mark.anyio
async def test_ingest_press_release_created_and_updated_are_mutually_exclusive(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        return make_pr_ingestion_result()

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    assert not (body["source_document_created"] and body["source_document_updated"])
    assert not (body["event_created"] and body["event_updated"])


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_press_release_external_service_error_returns_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        raise ExternalServiceError("openrouter", "upstream timeout")

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    response = await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)
    assert response.status_code == 502


@pytest.mark.anyio
async def test_ingest_press_release_502_has_structured_error_detail(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        raise ExternalServiceError("openrouter", "model rate limited")

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    assert "detail" in body
    assert body["detail"]["error"]["type"] == "external_service_error"
    assert body["detail"]["error"]["service"] == "openrouter"
    assert "message" in body["detail"]["error"]


@pytest.mark.anyio
async def test_ingest_press_release_validation_error_returns_422(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        raise ValidationError("Press release text cannot be empty.")

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    response = await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_ingest_press_release_service_validation_422_has_structured_detail(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self, text: str, source_url: str | None) -> PressReleaseIngestionResult:  # type: ignore[no-untyped-def]
        raise ValidationError("Press release text cannot be empty.")

    monkeypatch.setattr(_PR_SERVICE_PATH, _stub)

    body = (await client.post("/api/v1/jobs/ingest/press-release", json=_VALID_PAYLOAD)).json()
    assert "detail" in body
    assert body["detail"]["error"]["type"] == "validation_error"
    assert "message" in body["detail"]["error"]
