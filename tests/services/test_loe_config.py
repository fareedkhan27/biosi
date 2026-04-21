"""Tests for LOE proximity multiplier configuration."""

from datetime import date

import pytest

from app.core.loe_config import (
    LOE_MARKETS,
    apply_loe_multiplier_to_geography_score,
    calculate_loe_proximity_multiplier,
)


def test_expired_market_returns_max_multiplier() -> None:
    """India LOE is expired (None) → max multiplier 2.0."""
    assert calculate_loe_proximity_multiplier("india") == 2.0


def test_united_states_within_five_years() -> None:
    """US LOE is 2028-06; from 2026-04 that's ~2.2 years → 1.3 (≤5 bucket)."""
    assert calculate_loe_proximity_multiplier("united_states", reference_date=date(2026, 4, 1)) == 1.3


def test_eu_within_five_years() -> None:
    """EU LOE is ~2030; from 2026 that's ~4 years → 1.3."""
    assert calculate_loe_proximity_multiplier("eu", reference_date=date(2026, 4, 1)) == 1.3


def test_china_beyond_five_years() -> None:
    """China LOE is ~2032; from 2026 that's ~6 years → 1.0."""
    assert calculate_loe_proximity_multiplier("china", reference_date=date(2026, 4, 1)) == 1.0


def test_unknown_market_returns_neutral() -> None:
    """Unknown markets get 1.0 so they don't distort scoring."""
    assert calculate_loe_proximity_multiplier("mars") == 1.0
    assert calculate_loe_proximity_multiplier(None) == 1.0


def test_apply_multiplier_caps_at_30() -> None:
    """Geography score component must never exceed 30."""
    # India base=20 * 2.0 = 40, but capped at 30
    assert apply_loe_multiplier_to_geography_score(20, "india") == 30


def test_apply_multiplier_for_usa() -> None:
    """US base=16 * 1.3 = 21 (rounded)."""
    assert apply_loe_multiplier_to_geography_score(16, "united_states", reference_date=date(2026, 4, 1)) == 21


def test_loe_markets_has_all_expected_keys() -> None:
    expected = {"india", "united_states", "eu", "china", "japan", "global", "other", "unknown"}
    assert set(LOE_MARKETS.keys()) == expected
