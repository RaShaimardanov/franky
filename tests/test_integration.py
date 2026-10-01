from datetime import date
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from franky.catalog.parser import ListingEntry
from franky.catalog.sync import upsert_entries
from franky.config import GameSettings
from franky.db.models import EpisodeKind, GameStatus
from franky.db.repositories import Repos
from franky.services.game import GameService, GuessOutcome

ENTRIES = [
    ListingEntry(
        1, "Маяковский, Владимир Владимирович", EpisodeKind.REGULAR, date(2009, 8, 9), 2009
    ),
    ListingEntry(2, "Болан, Марк", EpisodeKind.REGULAR, None, 2006),
    ListingEntry(3, "Болан, Марк вер.2008", EpisodeKind.REGULAR, date(2008, 12, 7), 2008),
    ListingEntry(4, "Ошо (Раджниш, Чандра Мохан)", EpisodeKind.REGULAR, None, 2008),
    ListingEntry(5, "Презентация книги", EpisodeKind.SPECIAL, None, 2009),
]
USER_ID = 42


async def seed(session: AsyncSession, audio_dir: Path) -> Repos:
    for entry in ENTRIES:
        (audio_dir / f"{entry.site_id}.mp3").write_bytes(b"ID3")
    await upsert_entries(session, ENTRIES, audio_dir)
    repos = Repos(session)
    await repos.users.upsert(user_id=USER_ID, first_name="Тест", username=None, language_code="ru")
    await session.commit()
    return repos


async def test_sync_is_idempotent_and_groups_versions(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, tmp_path)
    report = await upsert_entries(session, ENTRIES, tmp_path)
    await session.commit()
    assert report.created == 0
    assert report.updated == len(ENTRIES)

    repos = Repos(session)
    bolan = await repos.characters.find_exact("Марк Болан")
    assert bolan is not None
    loaded = await repos.characters.get(bolan.id)
    assert loaded is not None
    assert sorted(e.site_id for e in loaded.episodes) == [2, 3]


async def test_search(session: AsyncSession, tmp_path: Path) -> None:
    repos = await seed(session, tmp_path)

    by_prefix = await repos.characters.search("маяк")
    assert [c.name for c in by_prefix][:1] == ["Владимир Владимирович Маяковский"]

    with_typo = await repos.characters.search("Маяковкий")
    assert "Владимир Владимирович Маяковский" in [c.name for c in with_typo]

    by_real_name = await repos.characters.search("раджниш")
    assert [c.name for c in by_real_name] == ["Ошо"]

    assert len(await repos.characters.search("")) == 3
    assert await repos.characters.search("zzzzzz") == []
    assert await repos.characters.search("100%_") == []  # спецсимволы LIKE экранированы


async def test_game_win_flow(session: AsyncSession, tmp_path: Path) -> None:
    repos = await seed(session, tmp_path)
    game = GameService(repos, GameSettings(max_attempts=3, max_hints=2))

    started = await game.start(USER_ID)
    assert started.is_new
    assert started.episode.kind is EpisodeKind.REGULAR  # праздничные выпуски не загадываются
    again = await game.start(USER_ID)
    assert not again.is_new
    assert again.game.id == started.game.id

    hint = await game.hint(USER_ID)
    assert hint.text is not None
    assert hint.hints_left == 1

    wrong = await game.guess(USER_ID, "Кто-то другой")
    assert wrong.outcome is GuessOutcome.WRONG
    assert wrong.attempts_left == 2

    character = started.episode.character
    assert character is not None
    answer = character.surname or character.name
    won = await game.guess(USER_ID, answer)
    assert won.outcome is GuessOutcome.CORRECT
    assert won.game is not None
    assert won.game.status is GameStatus.WON
    assert won.game.score == 1  # 3 − 1 ошибка − 1 подсказка
    await session.commit()

    stats = await repos.games.stats(USER_ID)
    assert (stats.games, stats.wins, stats.score, stats.best_streak, stats.rank) == (1, 1, 1, 1, 1)
    board = await repos.games.leaderboard()
    assert [(r.user_id, r.score) for r in board] == [(USER_ID, 1)]

    assert (await game.guess(USER_ID, answer)).outcome is GuessOutcome.NO_GAME


async def test_game_lose_and_surrender(session: AsyncSession, tmp_path: Path) -> None:
    repos = await seed(session, tmp_path)
    game = GameService(repos, GameSettings(max_attempts=2, max_hints=0))

    await game.start(USER_ID)
    assert (await game.hint(USER_ID)).text is None
    assert (await game.guess(USER_ID, "нет")).outcome is GuessOutcome.WRONG
    lost = await game.guess(USER_ID, "опять нет")
    assert lost.outcome is GuessOutcome.LOST
    assert lost.game is not None
    assert lost.game.score == 0

    second = await game.start(USER_ID)
    assert second.is_new
    assert second.episode.id != lost.game.episode_id  # сначала новые выпуски
    surrendered = await game.surrender(USER_ID)
    assert surrendered is not None
    assert surrendered.status is GameStatus.SURRENDERED
    await session.commit()

    stats = await repos.games.stats(USER_ID)
    assert (stats.games, stats.wins, stats.score, stats.rank) == (2, 0, 0, None)


async def test_favourites(session: AsyncSession, tmp_path: Path) -> None:
    repos = await seed(session, tmp_path)
    episode = await repos.episodes.pick_for_user(USER_ID)
    assert episode is not None

    assert await repos.favourites.toggle(USER_ID, episode.id) is True
    await session.commit()
    items, total = await repos.favourites.page(USER_ID, limit=10, offset=0)
    assert total == 1
    assert items[0].id == episode.id
    assert items[0].character is not None

    assert await repos.favourites.toggle(USER_ID, episode.id) is False
    await session.commit()
    assert not await repos.favourites.exists(USER_ID, episode.id)


async def test_versions_with_fuller_name_merge_into_one_character(
    session: AsyncSession, tmp_path: Path
) -> None:
    entries = [
        ListingEntry(10, "Лири, Тимоти", EpisodeKind.REGULAR, None, 2007),
        ListingEntry(11, "Лири, Тимоти Фрэнсис вер.2010", EpisodeKind.REGULAR, None, 2010),
    ]
    await upsert_entries(session, entries, tmp_path)
    await session.commit()
    repos = Repos(session)
    found = await repos.characters.search("лири")
    assert [c.name for c in found] == ["Тимоти Фрэнсис Лири"]
    assert await repos.characters.search("шопэн") == []
