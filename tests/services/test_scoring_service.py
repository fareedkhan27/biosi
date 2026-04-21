from __future__ import annotations

from app.services.scoring_service import (
    assign_traffic_light,
    calculate_threat_assessment,
    calculate_threat_score,
)


def test_assign_traffic_light_thresholds() -> None:
    assert assign_traffic_light(0) == "Green"
    assert assign_traffic_light(44) == "Green"
    assert assign_traffic_light(45) == "Amber"
    assert assign_traffic_light(74) == "Amber"
    assert assign_traffic_light(75) == "Red"
    assert assign_traffic_light(100) == "Red"


def test_calculate_threat_score_returns_int_and_clamped_range() -> None:
    score = calculate_threat_score(
        event_type="approval",
        development_stage="Phase 3",
        confidence_score=999,
        region="North America",
        country="United States",
    )

    assert isinstance(score, int)
    assert 0 <= score <= 100


def test_low_confidence_scores_lower_than_high_confidence_for_similar_inputs() -> None:
    low_confidence = calculate_threat_score(
        development_stage="Phase 2",
        competitor_tier=2,
        confidence_score=20,
        region="Europe",
        country="Germany",
        indication="RCC",
    )
    high_confidence = calculate_threat_score(
        development_stage="Phase 2",
        competitor_tier=2,
        confidence_score=90,
        region="Europe",
        country="Germany",
        indication="RCC",
    )

    assert low_confidence < high_confidence


def test_later_stage_higher_risk_scores_higher_than_early_stage() -> None:
    early_stage = calculate_threat_score(
        development_stage="Phase 1",
        competitor_tier=1,
        confidence_score=70,
        region="North America",
        country="United States",
        indication="NSCLC",
    )
    later_stage = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=1,
        confidence_score=70,
        region="North America",
        country="United States",
        indication="NSCLC",
    )

    assert early_stage < later_stage


def test_loe_multiplier_increases_india_score() -> None:
    india_score = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=2,
        confidence_score=70,
        country="India",
        indication="NSCLC",
    )
    baseline_score = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=2,
        confidence_score=70,
        indication="NSCLC",
    )

    assert india_score > baseline_score


def test_geography_weight_prioritizes_india_then_us_then_eu() -> None:
    india_score = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=2,
        confidence_score=70,
        country="India",
        indication="NSCLC",
    )
    us_score = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=2,
        confidence_score=70,
        country="United States",
        indication="NSCLC",
    )
    eu_score = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=2,
        confidence_score=70,
        country="Germany",
        indication="NSCLC",
    )

    assert india_score > us_score > eu_score


def test_tier_one_scores_higher_than_tier_four() -> None:
    tier_one_score = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=1,
        confidence_score=70,
        country="United States",
        indication="NSCLC",
    )
    tier_four_score = calculate_threat_score(
        development_stage="Phase 3",
        competitor_tier=4,
        confidence_score=70,
        country="United States",
        indication="NSCLC",
    )

    assert tier_one_score > tier_four_score


def test_phase_one_india_can_be_red_with_loe_multiplier() -> None:
    """India LOE is expired; even Phase 1 can hit Red due to 2.0 geography multiplier."""
    score = calculate_threat_score(
        development_stage="Phase 1",
        competitor_tier=1,
        confidence_score=95,
        country="India",
        indication="NSCLC",
    )

    # India geography base=20 * LOE multiplier 2.0 = 30 (capped)
    # 8 + 20 + 30 + 15 + 5 = 78
    assert score >= 75
    assert assign_traffic_light(score) == "Red"


def test_phase_one_usa_still_amber_without_loe_boost() -> None:
    """US LOE is ~2028; 1.6 multiplier keeps Phase 1 in Amber territory."""
    score = calculate_threat_score(
        development_stage="Phase 1",
        competitor_tier=1,
        confidence_score=95,
        country="United States",
        indication="NSCLC",
    )

    # US geography base=16 * LOE multiplier 1.6 = 26 (rounded)
    # 8 + 20 + 26 + 15 + 5 = 74
    assert score < 75
    assert assign_traffic_light(score) == "Amber"


def test_assessment_returns_auditable_breakdown() -> None:
    assessment = calculate_threat_assessment(
        development_stage="Phase 3",
        competitor_tier=None,
        confidence_score=70,
        country="India",
        indication=None,
    )

    assert assessment["score_breakdown"]["stage"] == 24
    # India LOE expired → 2.0 multiplier: 20 * 2.0 = 30 (capped at 30)
    assert assessment["score_breakdown"]["geography"] == 30
    assert "missing_competitor_profile" in assessment["score_breakdown"]["flags"]
    assert "missing_indication" in assessment["score_breakdown"]["flags"]
