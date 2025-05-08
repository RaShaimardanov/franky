from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from fluentogram import TranslatorRunner

from src.utils.fluent import configure_fluent, FluentService


class LangMiddleware(BaseMiddleware):
    """
    Cлужит для интеграции мультиязычной поддержки в телеграм-боте,
    используя данные о языке пользователя,
    что позволяет легко локализовать ответы и взаимодействие с ботом.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        event_from_user = data.get("event_from_user")
        fluent: FluentService = configure_fluent()
        translator_runner: TranslatorRunner = fluent.get_translator_by_locale(
            event_from_user.language_code
        )
        data["i18n"] = translator_runner
        return await handler(event, data)
