"""Каталог: алфавитный указатель персонажей с постраничной навигацией."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from franky.bot import keyboards, texts
from franky.bot.callbacks import CatalogCb
from franky.db.repositories import Repos
from franky.domain.catalog import build_index, paginate

PER_PAGE = 10


async def catalog(message: Message, repos: Repos) -> None:
    text, markup = await _render(repos, CatalogCb())
    await message.answer(text, reply_markup=markup)


async def navigate(callback: CallbackQuery, callback_data: CatalogCb, repos: Repos) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        text, markup = await _render(repos, callback_data)
        await callback.message.edit_text(text, reply_markup=markup)


async def _render(repos: Repos, state: CatalogCb) -> tuple[str, InlineKeyboardMarkup]:
    characters = await repos.characters.list_all()
    index = build_index(characters)
    if state.letter not in index:  # оглавление (или буква пропала после синхронизации)
        episodes = sum(len(c.episodes) for c in characters)
        return (
            texts.catalog_index(len(characters), episodes),
            keyboards.catalog_letters(list(index)),
        )

    section = index[state.letter]
    entries, page, pages = paginate(section, state.page, PER_PAGE)
    return (
        texts.catalog_letter(state.letter, len(section), page, pages),
        keyboards.catalog_page(entries, letter=state.letter, page=page, pages=pages),
    )


def create_router() -> Router:
    router = Router(name="catalog")
    router.message.register(catalog, Command("catalog"))
    router.message.register(catalog, F.text == texts.BTN_CATALOG)
    router.callback_query.register(navigate, CatalogCb.filter())
    return router
