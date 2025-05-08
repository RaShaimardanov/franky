import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from src.core.constants import DOWNLOAD_WAIT_TIMEOUT
from src.core.exceptions import (
    FileManagerError,
    DownloadTimeoutError,
)
from src.core.logger import logger


class FileManager:
    """Управление операциями с файлами."""

    def __init__(self, files_path: Path):
        self.files_path = files_path

    def get_file(self, file_name: str) -> Path:
        """Получение файла по file_name"""
        file_path = Path(self.files_path / file_name)
        if os.path.isfile(file_path):
            return file_path
        logger.error(f"Аудиофайл не найден: {file_path}")
        raise FileNotFoundError

    async def get_latest_downloaded_file(
        self, extension: str = ".crdownload"
    ) -> Optional[str]:
        """Получение последнего скачанного файла."""
        try:
            files = os.listdir(self.files_path)

            if not files:
                return None
            latest_file = max(
                [
                    os.path.join(self.files_path, f)
                    for f in files
                    if f.endswith(extension)
                ],
                key=os.path.getctime,
            )
            filename = os.path.basename(latest_file)
            return filename.removesuffix(extension)
        except Exception as e:
            raise FileManagerError(f"Ошибка получения файла: {e}") from e

    async def wait_for_downloads(self, timeout: int = DOWNLOAD_WAIT_TIMEOUT) -> None:
        """Ожидание завершения загрузки файлов с прогресс-баром."""
        start_time = datetime.now()
        logger.info(f"Началось ожидание завершения загрузки файлов: {start_time}")
        with tqdm(
            total=timeout,
            desc="Ожидание загрузок",
            unit="s",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} сек.",
        ) as pbar:
            while any(f.endswith(".crdownload") for f in os.listdir(self.files_path)):
                if (datetime.now() - start_time).seconds > timeout:
                    raise DownloadTimeoutError("Превышено время ожидания загрузки")
                await asyncio.sleep(1)
                pbar.update(1)
