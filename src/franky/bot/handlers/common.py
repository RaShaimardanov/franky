from pathlib import Path

import structlog
from aiogram import F, Router
from aiogram.filters import Command, CommandStart, ExceptionTypeFilter
from aiogram.types import ErrorEvent, FSInputFile, Message

from franky.bot import keyboards, texts
from franky.config import Settings
from franky.db.repositories import Repos

log = structlog.get_logger(__name__)


WELCOME_IMAGE = Path(__file__).resolve().parent.parent.parent / "assets" / "welcome.jpg"
_welcome_file_id: str | None = None  # после первой отправки шлём картинку по file_id


async def start(message: Message, settings: Settings) -> None:
    global _welcome_file_id
    sent = await message.answer_photo(
        _welcome_file_id or FSInputFile(WELCOME_IMAGE),
        caption=texts.start(settings.game.max_attempts),
        reply_markup=keyboards.main_menu(),
    )
    if sent.photo:
        _welcome_file_id = sent.photo[-1].file_id
    await message.answer(texts.SEARCH_PROMPT, reply_markup=keyboards.search_button())


async def stats(message: Message, repos: Repos) -> None:
    assert message.from_user
    await message.answer(texts.stats(await repos.games.stats(message.from_user.id)))


async def top(message: Message, repos: Repos) -> None:
    assert message.from_user
    rows = await repos.games.leaderboard()
    await message.answer(texts.leaderboard(rows, me=message.from_user.id))


async def on_error(event: ErrorEvent) -> None:
    log.error("update_failed", exc_info=event.exception, update_id=event.update.update_id)
    if event.update.callback_query:
        await event.update.callback_query.answer(texts.ERROR, show_alert=True)
    elif event.update.message:
        await event.update.message.answer(texts.ERROR)


def create_router() -> Router:
    router = Router(name="common")
    router.message.register(start, CommandStart())
    router.message.register(start, Command("help"))
    router.message.register(stats, Command("stats"))
    router.message.register(stats, F.text == texts.BTN_STATS)
    router.message.register(top, Command("top"))
    router.message.register(top, F.text == texts.BTN_TOP)
    router.errors.register(on_error, ExceptionTypeFilter(Exception))
    return router
