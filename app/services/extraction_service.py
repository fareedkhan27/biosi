from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.openrouter_service import OpenRouterService


class ExtractedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    competitor_name: str | None = None
    asset_code: str | None = None
    molecule_name: str | None = None
    reference_brand: str | None = None
    event_type: str | None = None
    event_subtype: str | None = None
    development_stage: str | None = None
    indication: str | None = None
    region: str | None = None
    country: str | None = None
    event_date: str | None = None
    summary: str | None = None
    evidence_excerpt: str | None = None
    confidence_score: int | None = None

    @field_validator(
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
        mode="before",
    )
    @classmethod
    def _coerce_unknown_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return None

        cleaned = value.strip()
        if not cleaned:
            return None

        lowered = cleaned.lower()
        if lowered in {"unknown", "n/a", "na", "null", "none", "not specified", "unspecified"}:
            return None
        return cleaned

    @field_validator("event_date", mode="after")
    @classmethod
    def _validate_event_date(cls, value: str | None) -> str | None:
        if value is None:
            return None

        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            return None

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _validate_confidence(cls, value: Any) -> int | None:
        if value is None:
            return None

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if not stripped.isdigit():
                return None
            value = int(stripped)

        if not isinstance(value, int):
            return None
        if value < 0 or value > 100:
            return None
        return value


def _get_openrouter_service() -> OpenRouterService:
    return OpenRouterService()


# Valid event_type values — must match scoring_service.py whitelist so full points are awarded.
VALID_EVENT_TYPES = (
    "trial_phase_change",
    "clinical_trial_update",
    "approval",
    "launch",
    "legal",
    "regulatory",
)

# Valid development_stage values — must contain "phase 3/2/1" substring for scoring to fire.
VALID_DEVELOPMENT_STAGES = (
    "Phase 1",
    "Phase 2",
    "Phase 3",
    "IND",
    "Approved",
    "Market Launch",
)


def _extraction_prompt(text: str, source_url: str | None) -> str:
    event_types = ", ".join(VALID_EVENT_TYPES)
    dev_stages = ", ".join(VALID_DEVELOPMENT_STAGES)
    return (
        "Extract one biosimilar competitive-intelligence event from the text below.\n"
        "Return STRICT JSON only — no markdown, no comments, no extra keys.\n"
        "\n"
        "FIELD DEFINITIONS:\n"
        "  competitor_name: string|null   — company name (e.g. 'Amgen', 'Henlius')\n"
        "  asset_code: string|null        — biosimilar asset code (e.g. 'ABP 206', 'HLX18')\n"
        "  molecule_name: string|null     — INN molecule name (e.g. 'nivolumab')\n"
        "  reference_brand: string|null   — originator brand (e.g. 'Opdivo')\n"
        f"  event_type: string|null        — MUST be one of: {event_types}; or null\n"
        "  event_subtype: string|null     — freeform sub-classification\n"
        f"  development_stage: string|null — MUST be one of: {dev_stages}; or null\n"
        "  indication: string|null        — disease/indication (e.g. 'NSCLC')\n"
        "  region: string|null            — geographic region (e.g. 'North America', 'Europe')\n"
        "  country: string|null           — specific country (e.g. 'United States', 'Germany')\n"
        "  event_date: YYYY-MM-DD|null    — ISO 8601 date or null\n"
        "  summary: string|null           — 1-3 sentence event summary\n"
        "  evidence_excerpt: string|null  — verbatim quote from the text supporting the event\n"
        "  confidence_score: integer 0-100|null — confidence in extraction accuracy\n"
        "\n"
        "RULES:\n"
        "- If a value is not explicitly stated, use null.\n"
        "- Do NOT invent dates, geographies, stages, brands, or competitor names.\n"
        "- event_type MUST be chosen from the enumerated list above, or null.\n"
        "- development_stage MUST be chosen from the enumerated list above, or null.\n"
        "- event_date must be YYYY-MM-DD format or null.\n"
        "- confidence_score must be integer 0-100 or null.\n"
        f"source_url: {source_url if source_url else 'null'}\n"
        "\n"
        "TEXT START\n"
        f"{text}\n"
        "TEXT END"
    )


async def extract_biosimilar_event_from_text(
    text: str,
    source_url: str | None = None,
) -> ExtractedEvent:
    prompt = _extraction_prompt(text=text, source_url=source_url)
    client = _get_openrouter_service()
    payload = await client.extract_json(prompt)
    return ExtractedEvent.model_validate(payload)
