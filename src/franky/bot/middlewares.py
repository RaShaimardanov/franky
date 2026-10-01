from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from franky.config import GameSettings
from franky.db.repositories import Repos
from franky.db.session import SessionFactory
from franky.services.game import GameService

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DatabaseMiddleware(BaseMiddleware):
    """Одна транзакция на апдейт: коммит при успехе, откат при исключении.

    Прокидывает в хендлеры `repos`, `game` и регистрирует/обновляет пользователя.
    """

    def __init__(self, session_factory: SessionFactory, game_settings: GameSettings) -> None:
        self._session_factory = session_factory
        self._game_settings = game_settings

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self._session_factory() as session, session.begin():
            repos = Repos(session)
            tg_user: User | None = data.get("event_from_user")
            if tg_user is not None and not tg_user.is_bot:
                await repos.users.upsert(
                    user_id=tg_user.id,
                    first_name=tg_user.first_name,
                    username=tg_user.username,
                    language_code=tg_user.language_code,
                )
            data["repos"] = repos
            data["game"] = GameService(repos, self._game_settings)
            return await handler(event, data)
