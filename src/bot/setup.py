from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from src.bot.handlers.start import router
from src.bot.middlewares.database import DatabaseMiddleware
from src.bot.middlewares.lang import LangMiddleware
from src.core.config import settings
from src.database.connect import async_session_pool


def _set_middlewares(dp: Dispatcher):
    """Подключение миддлвари к адептам"""
    dp.update.outer_middleware(
        DatabaseMiddleware(async_session_pool)
    )  # передаем данные для работы с БД в хендлеры
    dp.update.outer_middleware(
        LangMiddleware()
    )  # подключаем сервис локализации и передаем в хендлер


async def _set_main_menu(bot: Bot):
    """Создание список с командами и их описанием для кнопки menu"""
    main_menu_commands = [
        BotCommand(command="/show", description="Новый выпуск"),
        BotCommand(command="/favourites", description="Избранные выпуски"),
        BotCommand(command="/settings", description="Настройки"),
    ]

    await bot.set_my_commands(main_menu_commands)


def setup_bot() -> Bot:
    """Создание и настройка бота."""
    return Bot(
        token=settings.TELEGRAM.TOKEN,
        default=DefaultBotProperties(parse_mode=settings.TELEGRAM.PARSE_MODE),
    )


def setup_dispatcher() -> Dispatcher:
    """Создание и настройка диспетчера."""
    dp = Dispatcher()
    _set_middlewares(dp)
    dp.startup.register(_set_main_menu)
    dp.include_router(router)
    return dp
