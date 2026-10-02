from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class GameAct(StrEnum):
    HINT = "hint"
    SURRENDER = "give_up"
    NEXT = "next"
    RESEND = "resend"


class GameCb(CallbackData, prefix="g"):
    act: GameAct


class FavCb(CallbackData, prefix="f"):
    episode_id: int


class EpisodeCb(CallbackData, prefix="e"):
    episode_id: int


class CharacterCb(CallbackData, prefix="c"):
    character_id: int


class FavPageCb(CallbackData, prefix="fp"):
    page: int


class CatalogCb(CallbackData, prefix="cat"):
    letter: str = ""  # пусто — оглавление по буквам
    page: int = 0
