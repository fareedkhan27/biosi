from __future__ import annotations

import pytest

from app.services import extraction_service
from app.services.extraction_service import (
    VALID_DEVELOPMENT_STAGES,
    VALID_EVENT_TYPES,
    _extraction_prompt,
)


class _StubOpenRouterService:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def extract_json(self, prompt: str) -> dict[str, object]:
        assert "STRICT JSON" in prompt
        return self.payload


@pytest.mark.anyio
async def test_extract_biosimilar_event_from_text_maps_unknown_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "competitor_name": "unknown",
        "asset_code": "ABP 206",
        "molecule_name": "Nivolumab",
        "reference_brand": "Opdivo",
        "event_type": "trial update",
        "event_subtype": "phase advancement",
        "development_stage": "Phase 3",
        "indication": "NSCLC",
        "region": "n/a",
        "country": "",
        "event_date": "2026-06-15",
        "summary": "Company announced start of global phase 3 trial.",
        "evidence_excerpt": "...announced the first patient dosed in phase 3...",
        "confidence_score": 87,
    }

    monkeypatch.setattr(
        extraction_service,
        "_get_openrouter_service",
        lambda: _StubOpenRouterService(payload),
    )

    result = await extraction_service.extract_biosimilar_event_from_text(
        text="Press release text",
        source_url="https://example.com/press-release",
    )

    assert result.competitor_name is None
    assert result.asset_code == "ABP 206"
    assert result.region is None
    assert result.country is None
    assert result.event_date == "2026-06-15"
    assert result.confidence_score == 87


@pytest.mark.anyio
async def test_extract_biosimilar_event_from_text_drops_invalid_date_and_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "competitor_name": "Amgen",
        "event_type": "regulatory",
        "event_date": "2026-06",
        "confidence_score": 120,
    }

    monkeypatch.setattr(
        extraction_service,
        "_get_openrouter_service",
        lambda: _StubOpenRouterService(payload),
    )

    result = await extraction_service.extract_biosimilar_event_from_text(text="Another press release")

    assert result.competitor_name == "Amgen"
    assert result.event_date is None
    assert result.confidence_score is None


@pytest.mark.anyio
async def test_extract_biosimilar_event_from_text_ignores_unexpected_and_bad_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "competitor_name": 123,
        "event_date": "not-a-date",
        "confidence_score": "abc",
        "unexpected_key": "should-be-ignored",
    }

    monkeypatch.setattr(
        extraction_service,
        "_get_openrouter_service",
        lambda: _StubOpenRouterService(payload),
    )

    result = await extraction_service.extract_biosimilar_event_from_text(text="Bad payload sample")

    assert result.competitor_name is None
    assert result.event_date is None
    assert result.confidence_score is None
    assert not hasattr(result, "unexpected_key")


# ---------------------------------------------------------------------------
# Prompt alignment tests
# ---------------------------------------------------------------------------


def test_prompt_enumerates_all_valid_event_types() -> None:
    """Every scoring-relevant event_type must appear in the extraction prompt."""
    prompt = _extraction_prompt("sample text", None)
    for event_type in VALID_EVENT_TYPES:
        assert event_type in prompt, f"event_type '{event_type}' missing from prompt"


def test_prompt_enumerates_all_valid_development_stages() -> None:
    """Every development stage used by scoring must appear in the extraction prompt."""
    prompt = _extraction_prompt("sample text", None)
    for stage in VALID_DEVELOPMENT_STAGES:
        assert stage in prompt, f"development_stage '{stage}' missing from prompt"


def test_prompt_uses_real_newlines() -> None:
    """Prompt must use actual newline characters, not literal backslash-n."""
    prompt = _extraction_prompt("sample text", None)
    assert "\n" in prompt
    assert "\\n" not in prompt


def test_prompt_includes_source_url() -> None:
    prompt = _extraction_prompt("sample text", "https://example.com/release")
    assert "https://example.com/release" in prompt


def test_valid_event_types_align_with_scoring_whitelist() -> None:
    """event_types in VALID_EVENT_TYPES must score higher than 'unknown' event type."""
    from app.services.scoring_service import calculate_threat_score

    unknown_score = calculate_threat_score(event_type="totally_unknown_xyz")
    for event_type in VALID_EVENT_TYPES:
        score = calculate_threat_score(event_type=event_type)
        assert score > unknown_score, (
            f"'{event_type}' should score above baseline unknown, got {score} vs {unknown_score}"
        )
