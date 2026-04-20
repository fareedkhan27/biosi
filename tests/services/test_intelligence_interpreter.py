from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.intelligence_interpreter import build_competitor_summary, build_event_insight


def _make_event(
    *,
    competitor_name: str = "Amgen",
    threat_score: int = 82,
    traffic_light: str = "Red",
    development_stage: str = "Phase 3",
    indication: str = "NSCLC",
    country: str = "United States",
    region: str = "North America",
    competitor_tier: int | None = 1,
    flags: list[str] | None = None,
    confidence_component: int = 5,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        competitor_id=uuid.uuid4(),
        event_type="clinical_trial_update",
        title="Phase 3 milestone",
        event_date=date(2026, 4, 20),
        created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        review_status="approved",
        threat_score=threat_score,
        traffic_light=traffic_light,
        indication=indication,
        metadata_json={
            "competitor_name": competitor_name,
            "development_stage": development_stage,
            "indication": indication,
            "country": country,
            "region": region,
            "competitor_tier": competitor_tier,
            "score_breakdown": {
                "stage": 24,
                "competitor": 20,
                "geography": 16,
                "indication": 15,
                "confidence": confidence_component,
                "flags": flags or [],
            },
        },
    )


def test_build_event_insight_for_priority_red_event() -> None:
    event = _make_event()

    insight = build_event_insight(event)

    assert insight["summary"] is not None
    assert "high competitive pressure" in insight["summary"]
    assert "approaching LOE window" in insight["summary"]
    assert "primary extrapolation anchor" in insight["summary"]
    assert insight["risk_reason"] is not None
    assert "tier-1 competitor profile" in insight["risk_reason"]
    assert "late-stage development signal" in insight["risk_reason"]
    assert insight["recommended_action"] == (
        "Prepare indication-specific defense plan; monitor regulatory milestones"
    )
    assert insight["confidence_note"] == "High-confidence source signal."


def test_build_event_insight_for_medium_risk_event() -> None:
    event = _make_event(
        competitor_name="Henlius",
        threat_score=61,
        traffic_light="Amber",
        development_stage="Phase 2",
        indication="RCC",
        country="Germany",
        region="EU",
        competitor_tier=2,
        confidence_component=3,
    )

    insight = build_event_insight(event)

    assert insight["summary"] == (
        "Henlius progressing phase 2 in RCC (Germany) — potential competitive pressure; "
        "medium-term LOE (~2029–2030); secondary extrapolation risk"
    )
    assert insight["risk_reason"] is not None
    assert "mid-stage pipeline signal" in insight["risk_reason"]
    assert insight["recommended_action"] == "Track progression; validate indication overlap"
    assert insight["confidence_note"] is None


def test_build_event_insight_for_low_risk_event_is_not_alarmist() -> None:
    event = _make_event(
        competitor_name="Celltrion",
        threat_score=28,
        traffic_light="Green",
        development_stage="Phase 1",
        indication="Other/Extrapolation",
        country="Japan",
        region="APAC",
        competitor_tier=4,
        flags=["missing_competitor_profile"],
        confidence_component=2,
    )

    insight = build_event_insight(event)

    assert insight["summary"] == "Early-stage activity from Celltrion — low immediate risk"
    assert insight["risk_reason"] is not None
    assert "lower-tier competitor profile" in insight["risk_reason"]
    assert insight["recommended_action"] is None
    assert insight["confidence_note"] == "Interpret with caution: missing competitor profile."


def test_build_event_insight_handles_unknown_competitor() -> None:
    event = _make_event(competitor_name="", threat_score=55, traffic_light="Amber")
    event.metadata_json["competitor_name"] = None

    insight = build_event_insight(event)

    assert insight["summary"] is not None
    assert "Unknown competitor" in insight["summary"]
    assert insight["risk_reason"] is not None


def test_build_event_insight_handles_missing_indication() -> None:
    event = _make_event(indication=None, threat_score=58, traffic_light="Amber")
    event.indication = None
    event.metadata_json["indication"] = None

    insight = build_event_insight(event)

    assert insight["summary"] is not None
    assert "the lead indication" in insight["summary"]
    assert insight["recommended_action"] == "Track progression and complete indication/geography enrichment"


def test_build_event_insight_handles_missing_country() -> None:
    event = _make_event(country=None, region="Latin America", threat_score=62, traffic_light="Amber")
    event.metadata_json["country"] = None

    insight = build_event_insight(event)

    assert insight["summary"] is not None
    assert "(Latin America)" in insight["summary"]
    assert insight["risk_reason"] is not None


def test_build_event_insight_handles_new_geography() -> None:
    event = _make_event(country="Brazil", region="LATAM", threat_score=66, traffic_light="Amber")

    insight = build_event_insight(event)

    assert insight["summary"] is not None
    assert "(Brazil)" in insight["summary"]
    assert insight["risk_reason"] is not None
    assert "active in Brazil" in insight["risk_reason"]


def test_build_event_insight_low_confidence_note() -> None:
    event = _make_event(threat_score=63, traffic_light="Amber", confidence_component=1)

    insight = build_event_insight(event)

    assert insight["confidence_note"] == "Lower-confidence signal; corroborate with follow-up updates."


def test_build_competitor_summary_uses_highest_scoring_event() -> None:
    top_event = _make_event(competitor_name="Amgen", threat_score=82, traffic_light="Red")
    support_event = _make_event(
        competitor_name="Amgen",
        threat_score=57,
        traffic_light="Amber",
        development_stage="Phase 2",
        indication="Melanoma",
    )

    summary = build_competitor_summary([support_event, top_event])

    assert summary["competitor_name"] == "Amgen"
    assert summary["event_count"] == 2
    assert summary["max_score"] == 82
    assert summary["top_indication"] == "NSCLC"
    assert "Supported by 2 events in the current digest." in summary["summary"]
