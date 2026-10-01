import structlog
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from franky.bot import keyboards, texts
from franky.bot.callbacks import GameAct, GameCb
from franky.config import Settings
from franky.db.models import Game
from franky.db.repositories import Repos
from franky.services.audio import AudioSender, AudioUnavailableError
from franky.services.game import GameService, GuessOutcome, NoEpisodesError

log = structlog.get_logger(__name__)


async def play(
    message: Message, bot: Bot, game: GameService, audio: AudioSender, settings: Settings
) -> None:
    assert message.from_user
    await _start_game(message, bot, message.from_user.id, game, audio, settings)


async def next_game(
    callback: CallbackQuery, bot: Bot, game: GameService, audio: AudioSender, settings: Settings
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await _start_game(callback.message, bot, callback.from_user.id, game, audio, settings)


async def _start_game(
    message: Message,
    bot: Bot,
    user_id: int,
    game: GameService,
    audio: AudioSender,
    settings: Settings,
) -> None:
    try:
        started = await game.start(user_id)
    except NoEpisodesError:
        await message.answer(texts.NO_EPISODES)
        return

    if not started.is_new:
        await message.answer(texts.GAME_ALREADY_ACTIVE)

    attempts_left = settings.game.max_attempts - started.game.attempts
    hints_left = started.game.hints_used < settings.game.max_hints
    try:
        async with ChatActionSender.upload_document(chat_id=message.chat.id, bot=bot):
            await audio.send(
                message.chat.id,
                started.episode,
                caption=texts.game_caption(attempts_left),
                reply_markup=keyboards.game(hints_left=hints_left),
            )
    except AudioUnavailableError:
        log.exception("audio_unavailable", episode_id=started.episode.id)
        await game.cancel(started.game)  # загадка без аудио никому не нужна
        await message.answer(texts.AUDIO_FAILED)


async def hint(callback: CallbackQuery, game: GameService) -> None:
    result = await game.hint(callback.from_user.id)
    if result.game is None:
        await callback.answer(texts.NO_ACTIVE_GAME, show_alert=True)
        return
    if result.text is None:
        await callback.answer(texts.NO_MORE_HINTS, show_alert=True)
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        if not result.hints_left:
            await callback.message.edit_reply_markup(reply_markup=keyboards.game(hints_left=False))
        await callback.message.answer(texts.hint(result.text, result.hints_left))


async def surrender(callback: CallbackQuery, game: GameService, repos: Repos) -> None:
    finished = await game.surrender(callback.from_user.id)
    if finished is None:
        await callback.answer(texts.NO_ACTIVE_GAME, show_alert=True)
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await _reveal(callback.message, finished, repos)


async def handle_guess(message: Message, text: str, game: GameService, repos: Repos) -> bool:
    """Обрабатывает текст как ответ на загадку. False — если активной загадки нет."""
    assert message.from_user
    result = await game.guess(message.from_user.id, text)
    match result.outcome:
        case GuessOutcome.NO_GAME:
            return False
        case GuessOutcome.WRONG:
            await message.reply(texts.wrong_guess(text, result.attempts_left))
        case GuessOutcome.CORRECT | GuessOutcome.LOST:
            assert result.game
            await _reveal(message, result.game, repos)
    return True


async def _reveal(message: Message, finished: Game, repos: Repos) -> None:
    is_fav = await repos.favourites.exists(finished.user_id, finished.episode_id)
    await message.answer(
        texts.reveal(finished),
        reply_markup=keyboards.after_game(finished.episode_id, is_favourite=is_fav),
    )


def create_router() -> Router:
    router = Router(name="game")
    router.message.register(play, Command("play"))
    router.message.register(play, F.text == texts.BTN_PLAY)
    router.callback_query.register(next_game, GameCb.filter(F.act == GameAct.NEXT))
    router.callback_query.register(hint, GameCb.filter(F.act == GameAct.HINT))
    router.callback_query.register(surrender, GameCb.filter(F.act == GameAct.SURRENDER))
    return router
