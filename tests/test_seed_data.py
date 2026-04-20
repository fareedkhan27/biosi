"""Validates that demo seed data scores are consistent with the scoring service."""

from __future__ import annotations

import sys
import os

# Allow importing from scripts/ without making it a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.seeddemodata import DEMO_EVENTS, _compute_scores
from app.services.scoring_service import assign_traffic_light


def test_seed_scores_are_valid_and_consistent() -> None:
    """Threat scores stored in seed events must always be valid and have matching lights."""
    for seed in DEMO_EVENTS:
        computed_score, computed_light = _compute_scores(seed)
        assert 0 <= computed_score <= 100
        if seed.threat_score is not None and seed.traffic_light is not None:
            assert computed_score == seed.threat_score
            assert computed_light == seed.traffic_light
        else:
            assert computed_light == assign_traffic_light(computed_score)


def test_demo_events_cover_all_review_statuses() -> None:
    """Demo must include approved, pending, and rejected events for dashboard walkthrough."""
    statuses = {seed.review_status for seed in DEMO_EVENTS}
    assert "approved" in statuses, "Demo must have at least one approved event"
    assert "pending" in statuses, "Demo must have at least one pending event"
    assert "rejected" in statuses, "Demo must have at least one rejected event"


def test_demo_events_cover_multiple_traffic_lights() -> None:
    """Demo must include at least two distinct traffic light colours."""
    lights = {_compute_scores(seed)[1] for seed in DEMO_EVENTS}
    assert len(lights) >= 2, (
        f"Demo seed data only produces {lights}; need at least 2 distinct traffic lights for a useful demo"
    )


def test_approved_demo_events_have_non_null_scores() -> None:
    """Every approved event must have a non-null, in-range threat score."""
    for seed in DEMO_EVENTS:
        if seed.review_status == "approved":
            score, light = _compute_scores(seed)
            assert 0 <= score <= 100
            assert light in {"Green", "Amber", "Red"}


def test_all_demo_events_have_non_null_drug_name() -> None:
    for seed in DEMO_EVENTS:
        meta = seed.metadata_json or {}
        assert meta.get("drug_name") or meta.get("reference_drug_name")


def test_no_apac_shorthand_in_seed_regions() -> None:
    """Region values must not use the shorthand 'APAC' — scoring requires 'Asia-Pacific'."""
    for seed in DEMO_EVENTS:
        region = (seed.metadata_json or {}).get("region")
        assert region != "APAC", (
            f"'{seed.title[:50]}' uses 'APAC' — scoring service requires 'Asia-Pacific'"
        )
