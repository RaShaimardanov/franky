from typing import List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.utils.callback_data import UserSettingsCallback

kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Показать имя роли", callback_data="test")],
        [InlineKeyboardButton(text="Добавить в избранное", callback_data="test2")],
    ]
)


def back_kb() -> InlineKeyboardBuilder:
    """Кнопка « Назад"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="« Назад",
        callback_data="back",
    )
    builder.adjust(1)
    return builder


def build_keyboard(
    buttons: List[InlineKeyboardButton],
    width: int = 1,
    include_back: bool = False,
) -> InlineKeyboardMarkup:
    """Конструктор клавиатуры"""
    builder = InlineKeyboardBuilder()

    for button in buttons:
        builder.button(text=button.text, callback_data=button.callback_data)

    if include_back:
        builder.attach(back_kb())

    builder.adjust(width)
    return builder.as_markup()


def user_setting_kb(
    show_role_name: bool = False,
) -> InlineKeyboardMarkup:
    """Клавиатура меню настройки пользователя"""
    buttons = [
        InlineKeyboardButton(
            text="Скрыть имена ролей" if show_role_name else "Показывать имена ролей",
            callback_data=UserSettingsCallback(
                show_role_name=not show_role_name
            ).pack(),
        )
    ]
    return build_keyboard(buttons, include_back=True)
