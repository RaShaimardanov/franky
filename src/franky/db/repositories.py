"""Доступ к данным. Репозитории не коммитят — транзакцией управляет вызывающий код."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Float, and_, case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from franky.db.models import (
    Character,
    Episode,
    EpisodeKind,
    Favourite,
    Game,
    GameStatus,
    Guess,
    Transcript,
    User,
)
from franky.domain.names import normalize


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self, *, user_id: int, first_name: str, username: str | None, language_code: str | None
    ) -> User:
        values = {
            "first_name": first_name,
            "username": username,
            "language_code": language_code,
            "is_blocked": False,
        }
        stmt = (
            insert(User)
            .values(id=user_id, **values)
            .on_conflict_do_update(index_elements=[User.id], set_=values)
            .returning(User)
        )
        return (
            await self.session.scalars(stmt, execution_options={"populate_existing": True})
        ).one()


# Порог word_similarity для нечёткого поиска. Подобран на реальном архиве: «шопэн» → Шопен
# (0.5), «мерилин» → Мэрилин Монро (0.63), а случайный шум не выше ~0.4.
SEARCH_SIMILARITY = 0.45


class CharacterRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, character_id: int) -> Character | None:
        """Персонаж со списком выпусков. populate_existing — чтобы выпуски догрузились,
        даже если объект уже лежит в identity map сессии (иначе ленивая загрузка в async)."""
        stmt = (
            select(Character)
            .where(Character.id == character_id)
            .options(selectinload(Character.episodes))
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).first()

    async def list_all(self) -> Sequence[Character]:
        """Все персонажи с выпусками — для алфавитного указателя (их пара сотен)."""
        stmt = select(Character).options(selectinload(Character.episodes))
        return (await self.session.scalars(stmt)).all()

    async def search(self, query: str, *, limit: int = 20, offset: int = 0) -> Sequence[Character]:
        """Нечёткий поиск по всем вариантам имени (pg_trgm) с приоритетом совпадения по префиксу."""
        q = normalize(query)
        if not q:
            stmt = select(Character).order_by(Character.name).limit(limit).offset(offset)
            return (await self.session.scalars(stmt)).all()

        similarity = func.word_similarity(q, Character.search_text).cast(Float)
        contains = Character.search_text.contains(q, autoescape=True)
        # Какой-то из вариантов имени начинается с запроса: «маяк» → «|маяковский|».
        starts = case((Character.search_text.contains(f"|{q}", autoescape=True), 1), else_=0)
        stmt = (
            select(Character)
            .where(contains | (similarity >= SEARCH_SIMILARITY))
            .order_by(starts.desc(), contains.desc(), similarity.desc(), Character.name)
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()

    async def find_exact(self, text: str) -> Character | None:
        """Персонаж, у которого один из вариантов имени точно совпадает с текстом."""
        q = normalize(text)
        if not q:
            return None
        # Варианты имени в search_text обрамлены «|», так что это точное совпадение одного из них.
        stmt = select(Character).where(Character.search_text.contains(f"|{q}|", autoescape=True))
        return (await self.session.scalars(stmt.limit(1))).first()


def build_search_text(aliases: Sequence[str]) -> str:
    """Склеивает нормализованные алиасы как «|алиас1|алиас2|» для поиска и точного сравнения."""
    parts = dict.fromkeys(normalize(a) for a in aliases if normalize(a))
    return "|" + "|".join(parts) + "|"


class EpisodeRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, episode_id: int) -> Episode | None:
        return await self.session.get(Episode, episode_id)

    async def pick_for_user(self, user_id: int) -> Episode | None:
        """Случайный выпуск-загадка, которого пользователь ещё не слышал (если такие есть)."""
        played = select(Game.episode_id).where(Game.user_id == user_id)
        base = (
            select(Episode)
            .where(
                Episode.kind == EpisodeKind.REGULAR,
                Episode.character_id.isnot(None),
                (Episode.telegram_file_id.isnot(None)) | (Episode.audio_file.isnot(None)),
            )
            .order_by(func.random())
            .limit(1)
        )
        episode = (await self.session.scalars(base.where(Episode.id.not_in(played)))).first()
        return episode or (await self.session.scalars(base)).first()

    async def by_title(self, title: str) -> Episode | None:
        return (await self.session.scalars(select(Episode).where(Episode.title == title))).first()

    async def set_file_id(self, episode_id: int, file_id: str) -> None:
        episode = await self.session.get(Episode, episode_id)
        if episode:
            episode.telegram_file_id = file_id

    async def without_file_id(self) -> Sequence[Episode]:
        stmt = (
            select(Episode)
            .where(Episode.telegram_file_id.is_(None), Episode.audio_file.isnot(None))
            .order_by(Episode.site_id)
        )
        return (await self.session.scalars(stmt)).all()


@dataclass(frozen=True, slots=True)
class UserStats:
    games: int
    wins: int
    score: int
    best_streak: int
    rank: int | None


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    user_id: int
    first_name: str
    score: int
    wins: int


class GameRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active(self, user_id: int, *, for_update: bool = False) -> Game | None:
        stmt = select(Game).where(Game.user_id == user_id, Game.status == GameStatus.ACTIVE)
        if for_update:
            stmt = stmt.with_for_update(of=Game)
        return (await self.session.scalars(stmt)).first()

    async def create(self, user_id: int, episode_id: int) -> Game:
        game = Game(user_id=user_id, episode_id=episode_id, status=GameStatus.ACTIVE)
        self.session.add(game)
        await self.session.flush()
        return game

    async def add_guess(self, game: Game, text: str, *, is_correct: bool) -> None:
        self.session.add(Guess(game_id=game.id, text=text[:256], is_correct=is_correct))

    async def stats(self, user_id: int) -> UserStats:
        finished = and_(Game.user_id == user_id, Game.status != GameStatus.ACTIVE)
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(Game.status == GameStatus.WON),
                    func.coalesce(func.sum(Game.score), 0),
                ).where(finished)
            )
        ).one()
        statuses = (
            await self.session.scalars(
                select(Game.status).where(finished).order_by(Game.finished_at)
            )
        ).all()
        best = current = 0
        for status in statuses:
            current = current + 1 if status is GameStatus.WON else 0
            best = max(best, current)

        rank = None
        if row[2] > 0:
            totals = (
                select(Game.user_id, func.sum(Game.score).label("total"))
                .group_by(Game.user_id)
                .subquery()
            )
            higher = await self.session.scalar(
                select(func.count()).select_from(totals).where(totals.c.total > row[2])
            )
            rank = (higher or 0) + 1
        return UserStats(games=row[0], wins=row[1], score=row[2], best_streak=best, rank=rank)

    async def leaderboard(self, limit: int = 10) -> list[LeaderboardRow]:
        total = func.sum(Game.score).label("total")
        stmt = (
            select(
                User.id,
                User.first_name,
                total,
                func.count().filter(Game.status == GameStatus.WON),
            )
            .join(Game, Game.user_id == User.id)
            .group_by(User.id)
            .having(total > 0)
            .order_by(total.desc(), User.id)
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [LeaderboardRow(r[0], r[1], r[2], r[3]) for r in rows]


class FavouriteRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def toggle(self, user_id: int, episode_id: int) -> bool:
        """Добавляет/убирает выпуск из избранного. True — если теперь он в избранном."""
        existing = await self.session.get(Favourite, (user_id, episode_id))
        if existing:
            await self.session.delete(existing)
            return False
        await self.session.execute(
            insert(Favourite)
            .values(user_id=user_id, episode_id=episode_id)
            .on_conflict_do_nothing()
        )
        return True

    async def exists(self, user_id: int, episode_id: int) -> bool:
        return await self.session.get(Favourite, (user_id, episode_id)) is not None

    async def page(self, user_id: int, *, limit: int, offset: int) -> tuple[list[Episode], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(Favourite).where(Favourite.user_id == user_id)
        )
        stmt = (
            select(Episode)
            .join(Favourite, Favourite.episode_id == Episode.id)
            .where(Favourite.user_id == user_id)
            .order_by(Favourite.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.scalars(stmt)).all()), total or 0


@dataclass(frozen=True, slots=True)
class ContentHit:
    episode: Episode
    snippet: str


class TranscriptRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, episode_id: int, text: str, quotes: list[str]) -> None:
        stmt = insert(Transcript).values(episode_id=episode_id, text=text, quotes=quotes)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Transcript.episode_id],
                set_={"text": stmt.excluded.text, "quotes": stmt.excluded.quotes},
            )
        )

    async def quotes(self, episode_id: int) -> list[str]:
        found = await self.session.scalar(
            select(Transcript.quotes).where(Transcript.episode_id == episode_id)
        )
        return list(found or [])

    async def search(self, query: str, *, limit: int = 10, offset: int = 0) -> list[ContentHit]:
        """Полнотекстовый поиск по расшифровкам («джинн лампа», «Мулен Руж»)."""
        if not query.strip():
            return []
        tsquery = func.websearch_to_tsquery("russian", query)
        rank = func.ts_rank_cd(Transcript.search, tsquery)
        snippet = func.ts_headline(
            "russian",
            Transcript.text,
            tsquery,
            "MaxWords=18, MinWords=8, MaxFragments=1, StartSel=«, StopSel=»",
        )
        stmt = (
            select(Episode, snippet)
            .join(Transcript, Transcript.episode_id == Episode.id)
            .where(Transcript.search.op("@@")(tsquery))
            .order_by(rank.desc(), Episode.site_id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()
        return [ContentHit(episode=row[0], snippet=row[1]) for row in rows]


class Repos:
    """Набор репозиториев поверх одной сессии (одной транзакции)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepo(session)
        self.characters = CharacterRepo(session)
        self.episodes = EpisodeRepo(session)
        self.games = GameRepo(session)
        self.favourites = FavouriteRepo(session)
        self.transcripts = TranscriptRepo(session)
