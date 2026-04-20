"""Threat scoring helpers for biosimilar events.

Deterministic weighted model aligned to the Biosi strategy document.
"""

from __future__ import annotations

from typing import TypedDict


class ScoreBreakdown(TypedDict):
    stage: int
    competitor: int
    geography: int
    indication: int
    confidence: int
    flags: list[str]


class ThreatAssessment(TypedDict):
    threat_score: int
    traffic_light: str
    score_breakdown: ScoreBreakdown


_STAGE_WEIGHTS = {
    "phase_4": 30,
    "approval": 30,
    "market": 30,
    "launch": 30,
    "phase_3": 24,
    "phase_2": 16,
    "ind": 12,
    "phase_1": 8,
}

_COMPETITOR_TIER_WEIGHTS = {
    1: 20,
    2: 15,
    3: 10,
    4: 6,
}

_GEOGRAPHY_WEIGHTS = {
    "india": 20,
    "united_states": 16,
    "eu": 12,
    "china": 10,
    "japan": 6,
    "global": 6,
    "other": 8,
    "unknown": 8,
}

_INDICATION_WEIGHTS = {
    "nsclc": 15,
    "melanoma": 15,
    "rcc": 10,
    "scchn": 10,
    "other/extrapolation": 6,
    "unknown": 8,
}

_EU_COUNTRIES = {
    "austria",
    "belgium",
    "bulgaria",
    "croatia",
    "cyprus",
    "czech republic",
    "denmark",
    "estonia",
    "finland",
    "france",
    "germany",
    "greece",
    "hungary",
    "ireland",
    "italy",
    "latvia",
    "lithuania",
    "luxembourg",
    "malta",
    "netherlands",
    "poland",
    "portugal",
    "romania",
    "slovakia",
    "slovenia",
    "spain",
    "sweden",
    "united kingdom",
}


def _coerce_confidence_score(value: int | float | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _coerce_competitor_tier(value: int | float | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _resolve_loe_geography(
    *,
    region: str | None,
    country: str | None,
    competitor_geography: str | None = None,
) -> str | None:
    country_normalized = (country or "").strip().lower()
    region_normalized = (region or "").strip().lower()
    competitor_geography_normalized = (competitor_geography or "").strip().lower()

    if country_normalized in {"india"}:
        return "india"
    if country_normalized in {"united states", "usa", "us"}:
        return "united_states"
    if country_normalized == "china":
        return "china"
    if country_normalized == "japan":
        return "japan"
    if country_normalized in _EU_COUNTRIES or region_normalized in {"eu", "europe", "european union"}:
        return "eu"
    if region_normalized == "global":
        return "global"

    if "india" in competitor_geography_normalized:
        return "india"
    if any(token in competitor_geography_normalized for token in {"us", "united states", "usa"}):
        return "united_states"
    if "japan" in competitor_geography_normalized:
        return "japan"
    if "china" in competitor_geography_normalized:
        return "china"
    if any(token in competitor_geography_normalized for token in {"eu", "europe"}):
        return "eu"
    if competitor_geography_normalized == "global":
        return "global"
    return None


def _score_stage(development_stage: str | None) -> tuple[int, str | None]:
    stage_normalized = (development_stage or "").strip().lower()
    if "phase 4" in stage_normalized:
        return _STAGE_WEIGHTS["phase_4"], "phase_4"
    if stage_normalized in {"approval", "approved", "market", "market launch", "launch"}:
        return _STAGE_WEIGHTS["approval"], "approval"
    if "phase 3" in stage_normalized:
        return _STAGE_WEIGHTS["phase_3"], "phase_3"
    if "phase 2" in stage_normalized:
        return _STAGE_WEIGHTS["phase_2"], "phase_2"
    if stage_normalized == "ind":
        return _STAGE_WEIGHTS["ind"], "ind"
    if "phase 1" in stage_normalized:
        return _STAGE_WEIGHTS["phase_1"], "phase_1"
    return 14, None


def _score_competitor(competitor_tier: int | float | str | None) -> tuple[int, list[str]]:
    flags: list[str] = []
    tier = _coerce_competitor_tier(competitor_tier)
    if tier is None:
        flags.append("missing_competitor_profile")
        return 9, flags
    return _COMPETITOR_TIER_WEIGHTS.get(max(1, min(4, tier)), 9), flags


def _score_geography(
    *,
    region: str | None,
    country: str | None,
    competitor_geography: str | None,
) -> tuple[int, list[str]]:
    flags: list[str] = []
    geography_key = _resolve_loe_geography(
        region=region,
        country=country,
        competitor_geography=competitor_geography,
    )
    if geography_key is None:
        flags.append("missing_geography")
        return _GEOGRAPHY_WEIGHTS["unknown"], flags
    return _GEOGRAPHY_WEIGHTS.get(geography_key, _GEOGRAPHY_WEIGHTS["other"]), flags


def _score_indication(indication: str | None) -> tuple[int, list[str]]:
    indication_normalized = (indication or "").strip().lower()
    if not indication_normalized:
        return _INDICATION_WEIGHTS["unknown"], ["missing_indication"]
    if indication_normalized in {"nsclc", "melanoma", "rcc", "scchn", "other/extrapolation"}:
        return _INDICATION_WEIGHTS[indication_normalized], []
    return _INDICATION_WEIGHTS["other/extrapolation"], []


def _score_confidence(confidence_score: int | float | str | None) -> tuple[int, list[str]]:
    confidence = _coerce_confidence_score(confidence_score)
    if confidence is None:
        return 3, ["missing_confidence"]

    confidence = max(0, min(100, confidence))
    if confidence >= 90:
        return 5, []
    if confidence >= 75:
        return 4, []
    if confidence >= 60:
        return 3, []
    if confidence >= 40:
        return 2, []
    return 1, []


def calculate_threat_assessment(
    *,
    event_type: str | None = None,
    development_stage: str | None = None,
    competitor_tier: int | float | str | None = None,
    region: str | None = None,
    country: str | None = None,
    indication: str | None = None,
    confidence_score: int | float | str | None = None,
    competitor_geography: str | None = None,
    flags: list[str] | None = None,
) -> ThreatAssessment:
    """Return the normalized threat score and auditable component breakdown."""

    del event_type  # kept for backwards-compatible call sites

    stage_score, _ = _score_stage(development_stage)
    competitor_score, competitor_flags = _score_competitor(competitor_tier)
    geography_score, geography_flags = _score_geography(
        region=region,
        country=country,
        competitor_geography=competitor_geography,
    )
    indication_score, indication_flags = _score_indication(indication)
    confidence_score_value, confidence_flags = _score_confidence(confidence_score)

    breakdown_flags = list(flags or [])
    breakdown_flags.extend(competitor_flags)
    breakdown_flags.extend(geography_flags)
    breakdown_flags.extend(indication_flags)
    breakdown_flags.extend(confidence_flags)
    unique_flags = list(dict.fromkeys(breakdown_flags))

    total = min(
        100,
        stage_score + competitor_score + geography_score + indication_score + confidence_score_value,
    )
    traffic_light = assign_traffic_light(total)
    return {
        "threat_score": total,
        "traffic_light": traffic_light,
        "score_breakdown": {
            "stage": stage_score,
            "competitor": competitor_score,
            "geography": geography_score,
            "indication": indication_score,
            "confidence": confidence_score_value,
            "flags": unique_flags,
        },
    }


def calculate_threat_score(
    *,
    event_type: str | None = None,
    development_stage: str | None = None,
    competitor_tier: int | float | str | None = None,
    confidence_score: int | float | str | None = None,
    region: str | None = None,
    country: str | None = None,
    indication: str | None = None,
    competitor_geography: str | None = None,
) -> int:
    """Calculate a threat score in range [0, 100]."""

    assessment = calculate_threat_assessment(
        event_type=event_type,
        development_stage=development_stage,
        competitor_tier=competitor_tier,
        region=region,
        country=country,
        indication=indication,
        confidence_score=confidence_score,
        competitor_geography=competitor_geography,
    )
    return assessment["threat_score"]


def assign_traffic_light(threat_score: int | float) -> str:
    """Map score to traffic-light buckets.

    0-44: Green
    45-74: Amber
    75-100: Red
    """

    score = int(threat_score)
    if score <= 44:
        return "Green"
    if score <= 74:
        return "Amber"
    return "Red"
