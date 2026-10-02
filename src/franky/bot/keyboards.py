from collections.abc import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from franky.bot import texts
from franky.bot.callbacks import (
    CatalogCb,
    CharacterCb,
    EpisodeCb,
    FavCb,
    FavPageCb,
    GameAct,
    GameCb,
)
from franky.db.models import Character, Episode
from franky.domain.catalog import IndexEntry


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_PLAY), KeyboardButton(text=texts.BTN_CATALOG)],
            [
                KeyboardButton(text=texts.BTN_FAVOURITES),
                KeyboardButton(text=texts.BTN_STATS),
                KeyboardButton(text=texts.BTN_TOP),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def search_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[catalog_search_button()]])


def game(*, hints_left: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=texts.BTN_GUESS, switch_inline_query_current_chat="")
    if hints_left:
        kb.button(text=texts.BTN_HINT, callback_data=GameCb(act=GameAct.HINT))
    kb.button(text=texts.BTN_SURRENDER, callback_data=GameCb(act=GameAct.SURRENDER))
    kb.adjust(1, 2)
    return kb.as_markup()


def after_game(episode_id: int, *, is_favourite: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=texts.BTN_NEXT, callback_data=GameCb(act=GameAct.NEXT))
    kb.button(text=fav_label(is_favourite), callback_data=FavCb(episode_id=episode_id))
    kb.adjust(1)
    return kb.as_markup()


def episode(episode_id: int, *, is_favourite: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=fav_label(is_favourite), callback_data=FavCb(episode_id=episode_id))
    return kb.as_markup()


def characters(found: Sequence[Character]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for character in found:
        kb.button(text=character.name, callback_data=CharacterCb(character_id=character.id))
    kb.adjust(1)
    return kb.as_markup()


def episodes(items: Sequence[Episode]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(
            text=f"▶️ {texts.episode_button(item)}", callback_data=EpisodeCb(episode_id=item.id)
        )
    kb.adjust(1)
    return kb.as_markup()


def favourites(items: Sequence[Episode], *, page: int, pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.row(
            InlineKeyboardButton(
                text=f"▶️ {texts.episode_button(item)}",
                callback_data=EpisodeCb(episode_id=item.id).pack(),
            )
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=FavPageCb(page=page - 1).pack()))
    if pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=FavPageCb(page=page + 1).pack()))
    if nav:
        kb.row(*nav)
    return kb.as_markup()


def fav_label(is_favourite: bool) -> str:
    return "★ В избранном" if is_favourite else "☆ В избранное"


def catalog_search_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=texts.BTN_SEARCH, switch_inline_query_current_chat=texts.CATALOG_INLINE_PREFIX
    )


def catalog_letters(letters: Sequence[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for letter in letters:
        kb.button(text=letter, callback_data=CatalogCb(letter=letter))
    kb.adjust(6)
    kb.row(catalog_search_button())
    return kb.as_markup()


def catalog_page(
    entries: Sequence[IndexEntry[Character]], *, letter: str, page: int, pages: int
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for entry in entries:
        count = len(entry.item.episodes)
        title = f"{entry.title} ({count})" if count > 1 else entry.title
        kb.row(
            InlineKeyboardButton(
                text=title, callback_data=CharacterCb(character_id=entry.item.id).pack()
            )
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️", callback_data=CatalogCb(letter=letter, page=page - 1).pack()
            )
        )
    if pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="▶️", callback_data=CatalogCb(letter=letter, page=page + 1).pack()
            )
        )
    if nav:
        kb.row(*nav)
    kb.row(
        InlineKeyboardButton(text="🔤 Все буквы", callback_data=CatalogCb().pack()),
        catalog_search_button(),
    )
    return kb.as_markup()
