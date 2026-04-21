"""clean_malformed_review_status_and_traffic_light

Revision ID: 6cd156e98414
Revises: 20260420_0003
Create Date: 2026-04-22 00:33:22.227893

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "6cd156e98414"
down_revision: Union[str, None] = "20260420_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALID_REVIEW_STATUS = {"approved", "pending", "rejected"}
_VALID_TRAFFIC_LIGHT = {"Green", "Amber", "Red"}


def _normalize_review_status(value: str | None) -> str:
    raw = (value or "").strip()
    cleaned = raw.strip("\"'").strip().lower()
    if cleaned in _VALID_REVIEW_STATUS:
        return cleaned
    return "pending"


def _normalize_traffic_light(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip()
    cleaned = raw.strip("\"'").strip().lower()
    if not cleaned:
        return None
    canonical = cleaned.capitalize()
    if canonical in _VALID_TRAFFIC_LIGHT:
        return canonical
    return None


def upgrade() -> None:
    conn = op.get_bind()

    # -----------------------------------------------------------------------
    # Clean review_status
    # -----------------------------------------------------------------------
    result = conn.execute(
        text("SELECT DISTINCT review_status FROM events WHERE review_status IS NOT NULL")
    )
    for row in result:
        raw_status = row[0]
        normalized = _normalize_review_status(raw_status)
        if normalized != raw_status:
            conn.execute(
                text("UPDATE events SET review_status = :status WHERE review_status = :raw"),
                {"status": normalized, "raw": raw_status},
            )

    # -----------------------------------------------------------------------
    # Clean traffic_light
    # -----------------------------------------------------------------------
    result = conn.execute(
        text("SELECT DISTINCT traffic_light FROM events WHERE traffic_light IS NOT NULL")
    )
    for row in result:
        raw_light = row[0]
        normalized = _normalize_traffic_light(raw_light)
        if normalized is None:
            # Invalid traffic light values are set to NULL so downstream
            # scoring/rendering can treat them as unscored.
            conn.execute(
                text("UPDATE events SET traffic_light = NULL WHERE traffic_light = :raw"),
                {"raw": raw_light},
            )
        elif normalized != raw_light:
            conn.execute(
                text("UPDATE events SET traffic_light = :light WHERE traffic_light = :raw"),
                {"light": normalized, "raw": raw_light},
            )


def downgrade() -> None:
    # Data migration — irreversible.
    pass
