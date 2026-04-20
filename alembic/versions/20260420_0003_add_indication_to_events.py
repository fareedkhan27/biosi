"""Add indication to events and create biosimilar competitor profiles table.

Revision ID: 20260420_0003
Revises: 20260418_0002
Create Date: 2026-04-20 00:03:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260420_0003"
down_revision: str | None = "20260418_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("indication", sa.String(length=255), nullable=True))

    op.create_table(
        "biosimilar_competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("competitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("geography", sa.String(length=255), nullable=False),
        sa.Column("asset_name", sa.String(length=255), nullable=True),
        sa.Column("stage", sa.String(length=255), nullable=False),
        sa.Column("est_launch_year", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["competitor_id"],
            ["competitors.id"],
            name=op.f("fk_biosimilar_competitors_competitor_id_competitors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_biosimilar_competitors")),
        sa.UniqueConstraint("competitor_id", name=op.f("uq_biosimilar_competitors_competitor_id")),
        sa.UniqueConstraint("name", name=op.f("uq_biosimilar_competitors_name")),
    )
    op.create_index(
        op.f("ix_biosimilar_competitors_competitor_id"),
        "biosimilar_competitors",
        ["competitor_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_biosimilar_competitors_competitor_id"), table_name="biosimilar_competitors")
    op.drop_table("biosimilar_competitors")
    op.drop_column("events", "indication")
