"""Add threat_score, traffic_light, and review_status columns to events table (Milestone 2).

Revision ID: 20260418_0002
Revises: 20260418_0001
Create Date: 2026-04-18 00:02:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260418_0002"
down_revision: str | None = "20260418_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add three columns to events table for scoring and review workflow
    op.add_column("events", sa.Column("threat_score", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("traffic_light", sa.String(length=50), nullable=True))
    op.add_column(
        "events",
        sa.Column(
            "review_status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )

    # Create indexes for filtering and dashboard queries
    op.create_index(op.f("ix_events_threat_score"), "events", ["threat_score"], unique=False)
    op.create_index(op.f("ix_events_traffic_light"), "events", ["traffic_light"], unique=False)
    op.create_index(op.f("ix_events_review_status"), "events", ["review_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_events_review_status"), table_name="events")
    op.drop_index(op.f("ix_events_traffic_light"), table_name="events")
    op.drop_index(op.f("ix_events_threat_score"), table_name="events")

    op.drop_column("events", "review_status")
    op.drop_column("events", "traffic_light")
    op.drop_column("events", "threat_score")
