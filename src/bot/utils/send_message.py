from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from src.core.config import settings
from src.core.logger import logger

bot = Bot(
    token=settings.TELEGRAM.TOKEN,
    default=DefaultBotProperties(parse_mode=settings.TELEGRAM.PARSE_MODE),
)


async def notify_admin(text: str, chat_id=settings.TELEGRAM.ADMIN_CHAT_ID) -> None:
    """Уведомление администратору."""
    try:

        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {str(e)}")
