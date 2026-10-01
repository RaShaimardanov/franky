"""initial schema

Revision ID: 84d03a7dbc4d
Revises:
Create Date: 2026-10-02 01:41:14.775600
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "84d03a7dbc4d"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=256), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("surname", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("aliases", postgresql.ARRAY(sa.String(length=256)), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_characters")),
        sa.UniqueConstraint("key", name=op.f("uq_characters_key")),
    )
    op.create_index(
        "ix_characters_search_text_trgm",
        "characters",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "episodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "regular", "special", "fragment", name="episodekind", native_enum=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("aired_on", sa.Date(), nullable=True),
        sa.Column("aired_year", sa.Integer(), nullable=True),
        sa.Column("version", sa.String(length=16), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("audio_file", sa.String(length=256), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            name=op.f("fk_episodes_character_id_characters"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_episodes")),
        sa.UniqueConstraint("site_id", name=op.f("uq_episodes_site_id")),
    )
    op.create_index(op.f("ix_episodes_character_id"), "episodes", ["character_id"], unique=False)
    op.create_table(
        "favourites",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["episodes.id"],
            name=op.f("fk_favourites_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_favourites_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "episode_id", name=op.f("pk_favourites")),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "won",
                "lost",
                "surrendered",
                name="gamestatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["episodes.id"],
            name=op.f("fk_games_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_games_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_games")),
    )
    op.create_index(op.f("ix_games_user_id"), "games", ["user_id"], unique=False)
    op.create_index(
        "uq_games_active_per_user",
        "games",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "guesses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=256), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"], ["games.id"], name=op.f("fk_guesses_game_id_games"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guesses")),
    )
    op.create_index(op.f("ix_guesses_game_id"), "guesses", ["game_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_guesses_game_id"), table_name="guesses")
    op.drop_table("guesses")
    op.drop_index(
        "uq_games_active_per_user",
        table_name="games",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(op.f("ix_games_user_id"), table_name="games")
    op.drop_table("games")
    op.drop_table("favourites")
    op.drop_index(op.f("ix_episodes_character_id"), table_name="episodes")
    op.drop_table("episodes")
    op.drop_table("users")
    op.drop_index(
        "ix_characters_search_text_trgm",
        table_name="characters",
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.drop_table("characters")
