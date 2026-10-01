from collections.abc import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from franky.bot import texts
from franky.bot.callbacks import CharacterCb, EpisodeCb, FavCb, FavPageCb, GameAct, GameCb
from franky.db.models import Character, Episode


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_PLAY)],
            [
                KeyboardButton(text=texts.BTN_FAVOURITES),
                KeyboardButton(text=texts.BTN_STATS),
                KeyboardButton(text=texts.BTN_TOP),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def search_button(text: str = "🔎 Поиск по архиву") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, switch_inline_query_current_chat="")]]
    )


def game(*, hints_left: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔎 Угадать", switch_inline_query_current_chat="")
    if hints_left:
        kb.button(text="💡 Подсказка", callback_data=GameCb(act=GameAct.HINT))
    kb.button(text="🏳 Сдаться", callback_data=GameCb(act=GameAct.SURRENDER))
    kb.adjust(1, 2)
    return kb.as_markup()


def after_game(episode_id: int, *, is_favourite: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎲 Следующая загадка", callback_data=GameCb(act=GameAct.NEXT))
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
