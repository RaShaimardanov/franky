from aiogram import F, Router
from aiogram.enums import ChatType

from franky.bot.handlers import archive, catalog, common, game


def build_router() -> Router:
    """Собирает новое дерево роутеров (роутер aiogram можно подключить только к одному родителю)."""
    root = Router(name="root")
    # Бот рассчитан на личные чаты; inline-поиск работает где угодно.
    root.message.filter(F.chat.type == ChatType.PRIVATE)
    # Порядок важен: в archive последним стоит обработчик произвольного текста.
    root.include_routers(
        common.create_router(),
        game.create_router(),
        catalog.create_router(),
        archive.create_router(),
    )
    return root
