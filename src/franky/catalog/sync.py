"""Синхронизация каталога выпусков с сайтом и локальными файлами. Идемпотентна."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from franky.catalog.client import FshowClient
from franky.catalog.parser import ListingEntry
from franky.db.models import Character, Episode, EpisodeKind
from franky.db.repositories import build_search_text
from franky.db.session import SessionFactory
from franky.domain.names import CharacterName

log = structlog.get_logger(__name__)


def audio_filename(site_id: int) -> str:
    return f"{site_id}.mp3"


@dataclass(slots=True)
class SyncReport:
    created: int = 0
    updated: int = 0
    characters: int = 0
    removed: int = 0


async def sync_catalog(
    session_factory: SessionFactory, client: FshowClient, audio_dir: Path
) -> SyncReport:
    entries = await client.fetch_listing()
    async with session_factory() as session, session.begin():
        report = await upsert_entries(session, entries, audio_dir)
    log.info("catalog_synced", total=len(entries), **asdict(report))
    return report


async def upsert_entries(
    session: AsyncSession, entries: list[ListingEntry], audio_dir: Path
) -> SyncReport:
    report = SyncReport()
    characters = {c.key: c for c in (await session.scalars(select(Character))).all()}
    episodes = {e.site_id: e for e in (await session.scalars(select(Episode))).all()}

    # Персонаж собирается из всех его выпусков: имя берём самое полное, алиасы объединяем.
    names: dict[int, CharacterName] = {}
    by_key: dict[str, list[CharacterName]] = defaultdict(list)
    for entry in entries:
        if entry.kind is EpisodeKind.REGULAR:
            name = CharacterName.parse(entry.title)
            names[entry.site_id] = name
            by_key[name.key].append(name)

    for key, variants in by_key.items():
        character = characters.get(key)
        if character is None:
            character = characters[key] = Character(key=key)
            session.add(character)
            report.characters += 1
        _apply_names(character, variants)

    for entry in entries:
        episode = episodes.get(entry.site_id)
        if episode is None:
            episode = episodes[entry.site_id] = Episode(site_id=entry.site_id)
            session.add(episode)
            report.created += 1
        else:
            report.updated += 1

        parsed = names.get(entry.site_id)
        episode.title = entry.title
        episode.kind = entry.kind
        episode.aired_on = entry.aired_on
        episode.aired_year = entry.aired_year
        episode.version = parsed.version if parsed else None
        episode.character = characters[parsed.key] if parsed else None
        local = audio_dir / audio_filename(entry.site_id)
        if local.is_file():
            episode.audio_file = local.name

    await session.flush()
    # Персонажи, у которых не осталось выпусков (например, после смены ключа), не нужны в поиске.
    orphaned = await session.execute(
        delete(Character).where(~Character.episodes.any()).returning(Character.id)
    )
    report.removed = len(orphaned.all())
    return report


def _apply_names(character: Character, variants: list[CharacterName]) -> None:
    fullest = max(variants, key=lambda n: len(n.display))
    aliases = list(dict.fromkeys(alias for n in variants for alias in n.all_aliases))
    character.name = fullest.display
    character.surname = fullest.surname
    character.description = next((n.description for n in variants if n.description), None)
    character.aliases = aliases
    character.search_text = build_search_text(aliases)


async def download_missing(
    session_factory: SessionFactory,
    client: FshowClient,
    audio_dir: Path,
    *,
    limit: int | None = None,
) -> int:
    """Докачивает mp3 для выпусков, у которых ещё нет ни файла, ни file_id в Telegram."""
    async with session_factory() as session:
        stmt = (
            select(Episode.id, Episode.site_id)
            .where(Episode.audio_file.is_(None), Episode.telegram_file_id.is_(None))
            .order_by(Episode.site_id.desc())
        )
        pending = (await session.execute(stmt.limit(limit))).all()

    done = 0
    for episode_id, site_id in pending:
        target = audio_dir / audio_filename(site_id)
        try:
            if not target.is_file():
                await client.download(site_id, target)
        except Exception:
            log.exception("episode_download_failed", site_id=site_id)
            continue
        async with session_factory() as session, session.begin():
            episode = await session.get(Episode, episode_id)
            if episode:
                episode.audio_file = target.name
        done += 1
    return done
