"""Точка входа.

franky bot                    запустить бота (long polling)
franky sync                   обновить каталог выпусков с fshow.info
franky download [--limit N]   докачать mp3 для выпусков без файла
franky upload                 заранее залить аудио в Telegram и сохранить file_id
"""

import argparse
import asyncio
import contextlib
from collections.abc import Awaitable, Callable

import structlog

from franky.config import Settings, get_settings
from franky.db.session import SessionFactory, create_engine, create_session_factory
from franky.log_config import setup_logging

log = structlog.get_logger("franky")

Command = Callable[[Settings, SessionFactory, argparse.Namespace], Awaitable[None]]


async def run_bot(
    settings: Settings, session_factory: SessionFactory, _: argparse.Namespace
) -> None:
    from franky.bot.app import create_bot, create_dispatcher

    bot = create_bot(settings)
    dp = create_dispatcher(settings, session_factory, bot)
    log.info("bot_starting")
    async with bot:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def run_sync(
    settings: Settings, session_factory: SessionFactory, _: argparse.Namespace
) -> None:
    from franky.catalog.client import FshowClient
    from franky.catalog.sync import sync_catalog

    cat = settings.catalog
    async with FshowClient(cat.base_url, request_delay=cat.request_delay) as client:
        await sync_catalog(session_factory, client, cat.audio_dir)


async def run_download(
    settings: Settings, session_factory: SessionFactory, args: argparse.Namespace
) -> None:
    from franky.catalog.client import FshowClient
    from franky.catalog.sync import download_missing

    cat = settings.catalog
    async with FshowClient(cat.base_url, request_delay=cat.request_delay) as client:
        done = await download_missing(session_factory, client, cat.audio_dir, limit=args.limit)
    log.info("download_finished", downloaded=done)


async def run_upload(
    settings: Settings, session_factory: SessionFactory, _: argparse.Namespace
) -> None:
    """Загружает аудио в служебный чат, чтобы игроки получали выпуски мгновенно."""
    from franky.bot.app import create_bot
    from franky.db.repositories import Repos
    from franky.services.audio import AudioSender

    chat_id = settings.bot.storage_chat_id
    if chat_id is None:
        raise SystemExit("Задайте BOT__STORAGE_CHAT_ID — чат, куда бот может отправлять файлы")

    async with create_bot(settings) as bot:
        sender = AudioSender(bot, settings.catalog.audio_dir)
        async with session_factory() as session:
            pending = await Repos(session).episodes.without_file_id()
        for episode in pending:
            async with session_factory() as session, session.begin():
                episode = await session.merge(episode)
                try:
                    await sender.send(
                        chat_id, episode, caption=f"#{episode.site_id} {episode.title}"
                    )
                except Exception:
                    log.exception("upload_failed", site_id=episode.site_id)
                    continue
            log.info("uploaded", site_id=episode.site_id)
            await asyncio.sleep(3)  # не упираемся в лимиты Telegram


COMMANDS: dict[str, Command] = {
    "bot": run_bot,
    "sync": run_sync,
    "download": run_download,
    "upload": run_upload,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="franky", description="Бот «Фрэнки-шоу»")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bot", help="запустить бота")
    sub.add_parser("sync", help="обновить каталог выпусков с сайта")
    download = sub.add_parser("download", help="докачать недостающие mp3")
    download.add_argument("--limit", type=int, default=None, help="не больше N файлов")
    sub.add_parser("upload", help="заранее загрузить аудио в Telegram")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    setup_logging(settings.log_level, json=settings.log_json)
    engine = create_engine(settings.db)
    try:
        await COMMANDS[args.command](settings, create_session_factory(engine), args)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run(parse_args(argv)))


if __name__ == "__main__":
    main()
