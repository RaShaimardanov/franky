from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from franky.bot.handlers import build_router
from franky.bot.middlewares import DatabaseMiddleware
from franky.config import Settings
from franky.db.session import SessionFactory
from franky.services.audio import UPLOAD_LIMIT_BYTES, AudioSender

COMMANDS = [
    BotCommand(command="play", description="Новая загадка"),
    BotCommand(command="favourites", description="Избранные выпуски"),
    BotCommand(command="stats", description="Моя статистика"),
    BotCommand(command="top", description="Рейтинг знатоков"),
    BotCommand(command="help", description="Как играть"),
]


def create_bot(settings: Settings) -> Bot:
    session = None
    if settings.bot.api_server:
        session = AiohttpSession(api=TelegramAPIServer.from_base(settings.bot.api_server))
    return Bot(
        token=settings.bot.token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


def create_audio_sender(settings: Settings, bot: Bot) -> AudioSender:
    # Свой Bot API сервер принимает файлы до 2 ГБ — тогда сжимать не обязательно.
    limit = None if settings.bot.api_server else UPLOAD_LIMIT_BYTES
    return AudioSender(bot, settings.catalog.audio_dir, upload_limit=limit)


def create_dispatcher(settings: Settings, session_factory: SessionFactory, bot: Bot) -> Dispatcher:
    dp = Dispatcher(
        settings=settings,
        audio=create_audio_sender(settings, bot),
    )
    dp.update.outer_middleware(DatabaseMiddleware(session_factory, settings.game))
    dp.include_router(build_router())

    async def on_startup(bot: Bot) -> None:
        await bot.set_my_commands(COMMANDS)

    dp.startup.register(on_startup)
    return dp
