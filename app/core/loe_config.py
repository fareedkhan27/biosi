"""LOE (Loss of Exclusivity) configuration for geography-aware threat scoring.

Markets closer to LOE expiry receive higher proximity multipliers because
biosimilar entry becomes more imminent and commercially material.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class LoeMarketConfig:
    """LOE timeline and scoring multiplier for a single geography."""

    market_key: str
    loe_date: date | None
    """Expected LOE date; ``None`` means LOE has already expired."""
    base_multiplier: float
    """Hard-coded multiplier used when the dynamic calculation falls back."""


# ---------------------------------------------------------------------------
# Reference LOE dates for nivolumab (Opdivo) — primary Biosi reference brand.
# These are approximate industry consensus dates and may be updated.
# ---------------------------------------------------------------------------
# Markets with ``loe_date=None`` are treated as LOE-expired (open biosimilar entry).
# ``other`` and ``unknown`` use a sentinel far-future date so they stay neutral.
_FAR_FUTURE = date(2099, 1, 1)

LOE_MARKETS: dict[str, LoeMarketConfig] = {
    "india": LoeMarketConfig("india", None, 2.0),
    "united_states": LoeMarketConfig("united_states", date(2028, 6, 1), 1.6),
    "eu": LoeMarketConfig("eu", date(2030, 1, 1), 1.3),
    "china": LoeMarketConfig("china", date(2032, 1, 1), 1.0),
    "japan": LoeMarketConfig("japan", date(2033, 1, 1), 0.9),
    "global": LoeMarketConfig("global", None, 1.4),
    "other": LoeMarketConfig("other", _FAR_FUTURE, 1.0),
    "unknown": LoeMarketConfig("unknown", _FAR_FUTURE, 1.0),
}

# Bounds for dynamic proximity multiplier
_MIN_MULTIPLIER = 0.8
_MAX_MULTIPLIER = 2.0


def calculate_loe_proximity_multiplier(
    market_key: str | None,
    *,
    reference_date: date | None = None,
) -> float:
    """Return a multiplier in [0.8, 2.0] based on years to LOE.

    Logic
    -----
    - LOE already expired (``loe_date is None`` or past) → 2.0
    - ≤ 2 years to LOE → 1.6
    - ≤ 5 years to LOE → 1.3
    - > 5 years to LOE → 1.0
    - Unknown market → base multiplier from config, bounded by [_MIN, _MAX]
    """
    if market_key is None:
        return 1.0

    normalized = market_key.strip().lower()
    config = LOE_MARKETS.get(normalized)
    if config is None:
        return 1.0

    # LOE already expired
    if config.loe_date is None:
        return _MAX_MULTIPLIER

    reference = reference_date or date.today()
    if reference >= config.loe_date:
        return _MAX_MULTIPLIER

    years_to_loe = (config.loe_date - reference).days / 365.25

    if years_to_loe <= 2.0:
        return 1.6
    if years_to_loe <= 5.0:
        return 1.3
    return 1.0


def apply_loe_multiplier_to_geography_score(
    base_geography_score: int,
    market_key: str | None,
    *,
    reference_date: date | None = None,
) -> int:
    """Scale a base geography score by the LOE proximity multiplier.

    The result is rounded to the nearest integer and capped at 30 so that
    a single geography component cannot dominate the total score.
    """
    multiplier = calculate_loe_proximity_multiplier(
        market_key, reference_date=reference_date
    )
    scaled = round(base_geography_score * multiplier)
    return min(30, scaled)
