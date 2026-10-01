"""Отправка аудио выпусков. Файл грузится в Telegram один раз, дальше — по file_id."""

from pathlib import Path

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message

from franky.db.models import Episode

log = structlog.get_logger(__name__)

# Метаданные одинаковые для всех выпусков, чтобы плеер не выдавал ответ.
AUDIO_TITLE = "Кто я?"
AUDIO_PERFORMER = "Фрэнки-шоу"
AUDIO_FILENAME = "franky-show.mp3"


class AudioUnavailableError(Exception):
    pass


class AudioSender:
    def __init__(self, bot: Bot, audio_dir: Path) -> None:
        self._bot = bot
        self._audio_dir = audio_dir

    async def send(
        self,
        chat_id: int,
        episode: Episode,
        *,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message:
        """Отправляет выпуск. Если пришлось загружать файл, в episode.telegram_file_id
        появится новый file_id — его сохранит транзакция вызывающего кода."""
        if episode.telegram_file_id:
            try:
                return await self._bot.send_audio(
                    chat_id, episode.telegram_file_id, caption=caption, reply_markup=reply_markup
                )
            except TelegramBadRequest as exc:
                log.warning("stale_file_id", episode_id=episode.id, error=str(exc))
                episode.telegram_file_id = None

        message = await self._bot.send_audio(
            chat_id,
            self._local_file(episode),
            title=AUDIO_TITLE,
            performer=AUDIO_PERFORMER,
            caption=caption,
            reply_markup=reply_markup,
        )
        if message.audio is not None:
            episode.telegram_file_id = message.audio.file_id
        return message

    def _local_file(self, episode: Episode) -> FSInputFile:
        path = self._audio_dir / episode.audio_file if episode.audio_file else None
        if path is None or not path.is_file():
            raise AudioUnavailableError(f"Нет аудиофайла для выпуска {episode.id}")
        return FSInputFile(path, filename=AUDIO_FILENAME)
