"""add transcripts

Revision ID: 64254674a672
Revises: 84d03a7dbc4d
Create Date: 2026-10-02 07:45:30.168642
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "64254674a672"
down_revision: str | None = "84d03a7dbc4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("quotes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column(
            "search",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('russian', text)", persisted=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["episodes.id"],
            name=op.f("fk_transcripts_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("episode_id", name=op.f("pk_transcripts")),
    )
    op.create_index(
        "ix_transcripts_search", "transcripts", ["search"], unique=False, postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_transcripts_search", table_name="transcripts", postgresql_using="gin")
    op.drop_table("transcripts")
