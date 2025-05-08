import os
from pathlib import Path
from typing import Optional, Union

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, Message

from src.bot.utils.send_message import notify_admin
from src.core.constants import DEFAULT_AUDIO_TITLE, DEFAULT_AUDIO_PERFORMER
from src.core.exceptions import AudioFileNotFound, DatabaseError
from src.core.logger import logger
from src.core.paths import BROADCASTS_DIR
from src.database.models.broadcast import Broadcast
from src.database.models.user import User
from src.database.repo.requests import RequestsRepo
from src.services.filemanager import FileManager


class FileIDManager:
    """Управление Telegram file_id и их хранением в БД"""

    def __init__(self, repo: RequestsRepo, broadcast: Broadcast):
        self.broadcast = broadcast
        self._repo = repo

    async def get_file_id(self, use_alt: bool) -> Optional[str]:
        """Получить актуальный file_id из базы данных"""
        return (
            self.broadcast.telegram_file_id_alt
            if use_alt
            else self.broadcast.telegram_file_id
        )

    async def update_file_id(self, field: str, new_file_id: str) -> None:
        """Обновить file_id в базе данных"""
        try:
            await self._repo.broadcasts.update(self.broadcast, {field: new_file_id})
            logger.info(f"Обновлен {field} для Broadcast {self.broadcast.id}")
        except Exception as e:
            logger.error(f"Ошибка обновления {field}: {str(e)}")
            raise DatabaseError("Не удалось обновить file_id") from e


class AudioSender:
    """Отправка аудио с обработкой ошибок и повторами"""

    def __init__(
        self, bot: Bot, file_manager: FileManager, file_id_manager: FileIDManager
    ):
        self._bot = bot
        self._file_manager = file_manager
        self._file_id_manager = file_id_manager

    async def send(
        self,
        chat_id: int,
        filename: str,
        use_alt: bool,
        title: str,
    ) -> Optional[Message]:
        """Основной метод отправки аудио"""
        try:
            file_id = await self._file_id_manager.get_file_id(use_alt)
            if file_id:
                return await self._send_audio(chat_id, file_id, title)

            file_path = self._file_manager.get_file(filename)
            if file_path:
                return await self._send_local_file(chat_id, filename, use_alt, title)

            return None

        except TelegramBadRequest as e:
            if "wrong remote file identifier" in str(e):
                logger.warning(
                    f"Обнаружен невалидный file_id (ID {self._file_id_manager.broadcast.id}), отправляем локальный файл"
                )
                return await self._send_local_file(chat_id, filename, use_alt, title)

        except FileNotFoundError:
            error_message = f"Файл {filename} (ID) отсутствует на сервере"
            logger.exception(error_message)
            await notify_admin(text=error_message)
            return None

        except Exception as e:
            logger.error(e)

    async def _send_audio(self, chat_id: int, file_id: str, title: str) -> Message:
        """Отправка аудио через Telegram API"""

        return await self._bot.send_audio(
            chat_id=chat_id,
            audio=file_id,
            title=title,
            performer=DEFAULT_AUDIO_PERFORMER,
        )

    async def _send_local_file(
        self,
        chat_id: int,
        filename: str,
        use_alt: bool,
        title: str,
    ) -> Message:
        """Отправка локального файла с последующим сохранением file_id"""
        audio_source = self._file_manager.get_file(filename)
        message = await self._bot.send_audio(
            chat_id=chat_id,
            audio=FSInputFile(audio_source),
            title=title,
            performer=DEFAULT_AUDIO_PERFORMER,
        )

        field = "telegram_file_id_alt" if use_alt else "telegram_file_id"
        await self._file_id_manager.update_file_id(field, message.audio.file_id)
        return message


class AudioService:
    """Фасад для работы с аудио сервисом"""

    def __init__(self, user: User, broadcast: Broadcast, repo: RequestsRepo, bot: Bot):
        self._user = user
        self._bot = bot
        self._broadcast = broadcast

        self._file_manager = FileManager(files_path=BROADCASTS_DIR)
        self._file_id_manager = FileIDManager(repo=repo, broadcast=broadcast)

        self._sender = AudioSender(
            bot=bot,
            file_manager=self._file_manager,
            file_id_manager=self._file_id_manager,
        )

    async def send_audio(self) -> Message:
        """Публичный метод для отправки аудио"""
        sender = AudioSender(
            bot=self._bot,
            file_manager=self._file_manager,
            file_id_manager=self._file_id_manager,
        )
        return await sender.send(
            chat_id=self._user.telegram_id,
            filename=self._broadcast.filename,
            use_alt=self._user.show_role_name,
            title=self._get_audio_title(),
        )

    def _get_audio_title(self) -> str:
        """Генерация заголовка аудио"""
        return (
            self._broadcast.role_name
            if self._user.show_role_name
            else DEFAULT_AUDIO_TITLE
        )
