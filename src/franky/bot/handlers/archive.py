"""Архив: поиск персонажей, прослушивание выпусков с ответом, избранное."""

import math

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender

from franky.bot import keyboards, texts
from franky.bot.callbacks import CharacterCb, EpisodeCb, FavCb, FavPageCb
from franky.bot.handlers.game import handle_guess
from franky.db.models import Character
from franky.db.repositories import Repos
from franky.services.audio import AudioSender, AudioUnavailableError
from franky.services.game import GameService

INLINE_PAGE = 20
FAVOURITES_PAGE = 8
MAX_QUERY = 64


async def inline_search(query: InlineQuery, repos: Repos) -> None:
    """Подсказки имён по мере ввода. Выбранное имя уходит в чат обычным сообщением.

    Обычный режим («🔎 Угадать»): во время игры имя — это ответ, вне игры — поиск.
    Режим каталога (запрос начинается с «каталог: »): к имени добавляется метка 📚,
    и такое сообщение всегда открывает карточку персонажа, а не засчитывается как ответ.
    """
    text = query.query
    in_catalog = text.lower().startswith(texts.CATALOG_INLINE_PREFIX.strip())
    if in_catalog:
        text = text[len(texts.CATALOG_INLINE_PREFIX.strip()) :]
    mark = texts.CATALOG_MARK if in_catalog else ""

    offset = int(query.offset or 0)
    found = await repos.characters.search(text[:MAX_QUERY], limit=INLINE_PAGE, offset=offset)
    results = [
        InlineQueryResultArticle(
            id=f"{'c' if in_catalog else 'g'}{character.id}",
            title=character.name,
            description=character.description,
            input_message_content=InputTextMessageContent(message_text=mark + character.name),
        )
        for character in found
    ]
    await query.answer(
        results,  # type: ignore[arg-type]
        cache_time=300,
        is_personal=False,
        next_offset=str(offset + INLINE_PAGE) if len(found) == INLINE_PAGE else "",
    )


async def show_character(callback: CallbackQuery, callback_data: CharacterCb, repos: Repos) -> None:
    character = await repos.characters.get(callback_data.character_id)
    await callback.answer()
    if character is not None and isinstance(callback.message, Message):
        await _send_card(callback.message, character)


async def _send_card(message: Message, character: Character) -> None:
    episodes = sorted(character.episodes, key=lambda e: (e.aired_year or 0, e.site_id))
    await message.answer(texts.character_card(character), reply_markup=keyboards.episodes(episodes))


async def play_episode(
    callback: CallbackQuery,
    callback_data: EpisodeCb,
    bot: Bot,
    repos: Repos,
    game: GameService,
    audio: AudioSender,
) -> None:
    active = await game.active(callback.from_user.id)
    if active and active.episode_id == callback_data.episode_id:
        await callback.answer("Это твоя текущая загадка — сначала разгадай её 😉", show_alert=True)
        return
    episode = await repos.episodes.get(callback_data.episode_id)
    if episode is None:
        await callback.answer(texts.ERROR, show_alert=True)
        return
    await callback.answer()
    is_fav = await repos.favourites.exists(callback.from_user.id, episode.id)
    chat_id = callback.from_user.id
    try:
        async with ChatActionSender.upload_document(chat_id=chat_id, bot=bot):
            await audio.send(
                chat_id,
                episode,
                caption=texts.episode_caption(episode),
                reply_markup=keyboards.episode(episode.id, is_favourite=is_fav),
            )
    except AudioUnavailableError:
        await bot.send_message(chat_id, texts.AUDIO_FAILED)


async def toggle_favourite(callback: CallbackQuery, callback_data: FavCb, repos: Repos) -> None:
    added = await repos.favourites.toggle(callback.from_user.id, callback_data.episode_id)
    await callback.answer(texts.FAV_ADDED if added else texts.FAV_REMOVED)
    message = callback.message
    if isinstance(message, Message) and message.reply_markup:
        await message.edit_reply_markup(
            reply_markup=_with_fav_label(message.reply_markup, callback.data or "", added)
        )


def _with_fav_label(markup: InlineKeyboardMarkup, data: str, added: bool) -> InlineKeyboardMarkup:
    """Меняет подпись только у кнопки избранного, не трогая остальную клавиатуру."""
    rows = [
        [
            btn.model_copy(update={"text": keyboards.fav_label(added)})
            if btn.callback_data == data
            else btn
            for btn in row
        ]
        for row in markup.inline_keyboard
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def favourites(message: Message, repos: Repos) -> None:
    assert message.from_user
    text, markup = await _favourites_page(repos, message.from_user.id, page=0)
    await message.answer(text, reply_markup=markup)


async def favourites_page(callback: CallbackQuery, callback_data: FavPageCb, repos: Repos) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        text, markup = await _favourites_page(repos, callback.from_user.id, callback_data.page)
        await callback.message.edit_text(text, reply_markup=markup)


async def _favourites_page(
    repos: Repos, user_id: int, page: int
) -> tuple[str, InlineKeyboardMarkup | None]:
    items, total = await repos.favourites.page(
        user_id, limit=FAVOURITES_PAGE, offset=page * FAVOURITES_PAGE
    )
    if total == 0:
        return texts.FAVOURITES_EMPTY, None
    pages = math.ceil(total / FAVOURITES_PAGE)
    markup = keyboards.favourites(items, page=page, pages=pages)
    return texts.FAVOURITES_TITLE.format(total=total), markup


async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


async def free_text(message: Message, repos: Repos, game: GameService) -> None:
    """Любой текст: ответ на загадку, если она идёт, иначе — поиск по архиву."""
    assert message.text
    if message.text.startswith(texts.CATALOG_MARK):  # выбрано в поиске по каталогу
        name = message.text.removeprefix(texts.CATALOG_MARK).strip()
        found_exact = await repos.characters.find_exact(name)
        if found_exact and (character := await repos.characters.get(found_exact.id)):
            await _send_card(message, character)
            return

    query = message.text.strip()[:MAX_QUERY]
    if await handle_guess(message, query, game, repos):
        return

    if exact := await repos.characters.find_exact(query):
        found = [exact]
    else:
        found = list(await repos.characters.search(query, limit=10))
    if not found:
        await message.answer(texts.search_empty(query), reply_markup=keyboards.search_button())
        return
    await message.answer(texts.SEARCH_RESULTS, reply_markup=keyboards.characters(found))


def create_router() -> Router:
    router = Router(name="archive")
    router.inline_query.register(inline_search)
    router.callback_query.register(show_character, CharacterCb.filter())
    router.callback_query.register(play_episode, EpisodeCb.filter())
    router.callback_query.register(toggle_favourite, FavCb.filter())
    router.callback_query.register(favourites_page, FavPageCb.filter())
    router.callback_query.register(noop, F.data == "noop")
    router.message.register(favourites, Command("favourites"))
    router.message.register(favourites, F.text == texts.BTN_FAVOURITES)
    # Последним: любой текст — ответ на загадку или поиск по архиву.
    router.message.register(free_text, F.text, ~F.text.startswith("/"))
    return router
