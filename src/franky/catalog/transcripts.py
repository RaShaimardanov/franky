"""Импорт расшифровок выпусков (JSON от Whisper) в базу. Повторный запуск безопасен.

Формат файла `<site_id>.json`:
    {"site_id": 47, "duration": 2868.4, "segments": [{"start": 0.0, "end": 5.1, "text": "..."}]}
"""

import json
from pathlib import Path

import structlog
from sqlalchemy import select

from franky.db.models import Episode
from franky.db.repositories import Repos
from franky.db.session import SessionFactory
from franky.domain.quotes import Segment, extract_quotes

log = structlog.get_logger(__name__)


async def import_transcripts(session_factory: SessionFactory, directory: Path) -> int:
    files = sorted(directory.glob("*.json"))
    async with session_factory() as session, session.begin():
        repos = Repos(session)
        episodes = {e.site_id: e for e in (await session.scalars(select(Episode))).all()}
        imported = 0
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            episode = episodes.get(int(data["site_id"]))
            if episode is None:
                log.warning("transcript_without_episode", file=path.name)
                continue
            segments = [Segment(s["start"], s["text"]) for s in data["segments"]]
            names = episode.character.aliases if episode.character else [episode.title]
            quotes = extract_quotes(segments, float(data["duration"]), names)
            text = " ".join(s.text for s in segments)
            await repos.transcripts.upsert(episode.id, text, quotes)
            imported += 1
    log.info("transcripts_imported", imported=imported, files=len(files))
    return imported
