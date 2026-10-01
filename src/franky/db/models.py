from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enum(enum_cls: type[StrEnum]) -> Enum:
    # Храним как VARCHAR: новые значения не требуют ALTER TYPE в миграциях.
    return Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class EpisodeKind(StrEnum):
    REGULAR = "regular"  # обычный выпуск-загадка
    SPECIAL = "special"  # «ПРАЗДНИК»
    FRAGMENT = "fragment"  # «ФРАГМЕНТ»


class GameStatus(StrEnum):
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"
    SURRENDERED = "surrendered"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64))
    language_code: Mapped[str | None] = mapped_column(String(16))
    is_blocked: Mapped[bool] = mapped_column(server_default=text("false"))


class Character(TimestampMixin, Base):
    """Знаменитость, чью жизнь «прожил» ведущий. У одного персонажа бывает несколько выпусков."""

    __tablename__ = "characters"
    __table_args__ = (
        Index(
            "ix_characters_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(256), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    surname: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(256)))
    # Нормализованные варианты имени через пробел — по ним работает триграммный поиск.
    search_text: Mapped[str] = mapped_column(Text)

    episodes: Mapped[list["Episode"]] = relationship(back_populates="character")


class Episode(TimestampMixin, Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, unique=True)  # id на fshow.info
    title: Mapped[str] = mapped_column(String(512))  # заголовок как на сайте
    kind: Mapped[EpisodeKind] = mapped_column(_enum(EpisodeKind))
    aired_on: Mapped[date | None] = mapped_column(Date)
    aired_year: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[str | None] = mapped_column(String(16))
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"), index=True
    )
    audio_file: Mapped[str | None] = mapped_column(String(256))
    telegram_file_id: Mapped[str | None] = mapped_column(String(256))

    # many-to-one: дешёвый JOIN, зато к персонажу можно обращаться без ленивой загрузки в async.
    character: Mapped[Character | None] = relationship(back_populates="episodes", lazy="joined")

    @property
    def is_playable(self) -> bool:
        return self.kind is EpisodeKind.REGULAR and self.character_id is not None


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        # У пользователя может быть только одна незавершённая загадка.
        Index(
            "uq_games_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    status: Mapped[GameStatus] = mapped_column(_enum(GameStatus), default=GameStatus.ACTIVE)
    attempts: Mapped[int] = mapped_column(default=0)
    hints_used: Mapped[int] = mapped_column(default=0)
    score: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    episode: Mapped[Episode] = relationship(lazy="joined")


class Guess(TimestampMixin, Base):
    __tablename__ = "guesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(256))
    is_correct: Mapped[bool]


class Favourite(TimestampMixin, Base):
    __tablename__ = "favourites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), primary_key=True
    )

    episode: Mapped[Episode] = relationship(lazy="joined")
