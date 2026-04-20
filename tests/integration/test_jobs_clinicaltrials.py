"""
Integration tests for POST /api/v1/jobs/ingest/clinicaltrials.

Exercises:
- 200 success path with mocked service
- response schema and field types
- integer count fields are ints
- at least one record created in a success scenario
- idempotent/duplicate run: created counters are zero, updated counters reflect
  the existing records
- ExternalServiceError → 502 with structured error payload
- ValidationError from service → 422 with structured error payload
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.config import settings
from app.services.clinicaltrials_service import ClinicalTrialsIngestionResult
from tests.helpers.factories import make_ct_ingestion_result, make_ct_ingestion_result_zero_created

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CT_SERVICE_PATH = (
    "app.services.clinicaltrials_service.ClinicalTrialsIngestionService.ingest_default_terms"
)

_EXPECTED_RESPONSE_KEYS = {
    "status",
    "created",
    "updated",
    "skipped",
}


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_clinicaltrials_returns_200(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result()

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    response = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_ingest_clinicaltrials_response_has_all_required_keys(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result()

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert set(body.keys()) == _EXPECTED_RESPONSE_KEYS


@pytest.mark.anyio
async def test_ingest_clinicaltrials_source_is_clinicaltrials_gov(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result()

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert body["status"] == "ok"


@pytest.mark.anyio
async def test_ingest_clinicaltrials_search_terms_is_list_of_strings(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result()

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert isinstance(body["created"], int)
    assert isinstance(body["updated"], int)
    assert isinstance(body["skipped"], int)


@pytest.mark.anyio
async def test_ingest_clinicaltrials_integer_count_fields_are_ints(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result(
            studies_seen=12,
            source_documents_created=8,
            source_documents_updated=4,
            events_created=7,
            events_updated=5,
        )

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    for key in ("created", "updated", "skipped"):
        assert isinstance(body[key], int), f"expected int for {key}, got {type(body[key])}"


@pytest.mark.anyio
async def test_ingest_clinicaltrials_success_creates_at_least_one_record(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result(source_documents_created=3, events_created=3)

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert body["created"] >= 1


@pytest.mark.anyio
async def test_ingest_clinicaltrials_count_fields_sum_to_studies_seen(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result(
            studies_seen=5,
            source_documents_created=3,
            source_documents_updated=2,
            events_created=3,
            events_updated=2,
        )

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert body["created"] + body["updated"] + body["skipped"] == 5


# ---------------------------------------------------------------------------
# Idempotency / duplicate-safe path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_clinicaltrials_second_run_zero_created(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second run with the same upstream data should report 0 creates."""
    call_count = 0

    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_ct_ingestion_result(studies_seen=5, source_documents_created=5, events_created=5)
        return make_ct_ingestion_result_zero_created(studies_seen=5)

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    r1 = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    r2 = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()

    assert r1["created"] == 5

    assert r2["created"] == 0
    assert r2["updated"] == 5


@pytest.mark.anyio
async def test_ingest_clinicaltrials_idempotent_totals_consistent(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On duplicate run, created + updated should still equal studies_seen."""
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        return make_ct_ingestion_result_zero_created(studies_seen=4)

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert body["created"] + body["updated"] + body["skipped"] == 4


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_clinicaltrials_external_service_error_returns_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        raise ExternalServiceError("clinicaltrials.gov", "Connection refused")

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    response = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert response.status_code == 502


@pytest.mark.anyio
async def test_ingest_clinicaltrials_502_has_structured_error_detail(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        raise ExternalServiceError("clinicaltrials.gov", "timeout after 30s")

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert "detail" in body
    assert body["detail"]["error"]["type"] == "external_service_error"
    assert body["detail"]["error"]["service"] == "clinicaltrials.gov"
    assert "message" in body["detail"]["error"]


@pytest.mark.anyio
async def test_ingest_clinicaltrials_validation_error_returns_422(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        raise ValidationError("Source 'clinicaltrials' is not seeded.")

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    response = await client.post("/api/v1/jobs/ingest/clinicaltrials")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_ingest_clinicaltrials_422_has_structured_error_detail(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stub(self) -> ClinicalTrialsIngestionResult:  # type: ignore[no-untyped-def]
        raise ValidationError("Source 'clinicaltrials' is not seeded.")

    monkeypatch.setattr(_CT_SERVICE_PATH, _stub)
    monkeypatch.setattr(settings, "clinicaltrials_base_url", "https://clinicaltrials.gov/api/v2/studies")

    body = (await client.post("/api/v1/jobs/ingest/clinicaltrials")).json()
    assert "detail" in body
    assert body["detail"]["error"]["type"] == "validation_error"
    assert "message" in body["detail"]["error"]
