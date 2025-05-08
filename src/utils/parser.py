import asyncio
import logging
import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio
from webdriver_manager.chrome import ChromeDriverManager

from src.core.constants import (
    START_URL,
    PAUSE_DURATION_SECONDS,
    DOWNLOAD_WAIT_TIMEOUT,
    DRIVER_TIMEOUT,
)

from src.core.paths import BROADCASTS_DIR
from src.core.exceptions import (
    WebDriverError,
    LinkProcessingError,
    DatabaseError,
    FileManagerError,
    PageParsingError,
    DownloadTimeoutError,
)
from src.database.connect import async_session_pool
from src.database.repo.requests import RequestsRepo
from src.utils.enums import ReleaseType

logger = logging.getLogger(__name__)


class WebDriverManager:
    """Управление веб-драйвером с использованием контекстного менеджера."""

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None

    async def __aenter__(self) -> webdriver.Chrome:
        """Инициализация и настройка веб-драйвера."""
        try:
            service = Service(executable_path=ChromeDriverManager().install())
            chrome_options = self._configure_chrome_options()
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            return self.driver
        except Exception as e:
            raise WebDriverError(f"Ошибка при инициализации веб-драйвера: {e}") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Гарантированное закрытие драйвера"""
        if self.driver:
            self.driver.quit()

    @staticmethod
    def _configure_chrome_options() -> webdriver.ChromeOptions:
        """Конфигурация опций Chrome."""
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument("--headless=new")
        # chrome_options.add_argument("--no-sandbox")
        # chrome_options.add_argument("--disable-dev-shm-usage")

        prefs = {
            "download.default_directory": str(BROADCASTS_DIR),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        return chrome_options


class LinkProcessor:
    """Обработка текста ссылки для извлечения данных."""

    _LINK_PATTERN = re.compile(
        r"(?P<release_date>\d{2}\.\d{2}\.\d{2}|=\d{4}=)\s*(\((?P<release_type>[^)]+)\)\s*)?(?P<role_name>.+)"
    )

    @classmethod
    async def process_link(cls, link_text: str) -> Optional[Dict[str, Any]]:
        """Парсинг информации из текста ссылки."""
        try:
            await asyncio.sleep(PAUSE_DURATION_SECONDS)
            if not (link_data := cls._LINK_PATTERN.match(link_text)):
                raise ValueError(f"Invalid link format: {link_text}")
            return link_data.groupdict()
        except Exception as e:
            raise LinkProcessingError(f"Ошибка при обработке ссылки: {e}") from e


class DatabaseManager:
    """Управление операциями с базой данных."""

    @staticmethod
    async def _parse_release_date(date_str: str) -> date | None:
        """Парсинг даты из строки."""
        try:
            return datetime.strptime(date_str, "%d.%m.%y").date()
        except ValueError:
            return None

    @classmethod
    async def save_broadcast_data(
        cls, link_data: Dict[str, Any], repo: RequestsRepo
    ) -> None:
        """Сохранение данных трансляции в БД."""
        try:
            data = {
                "role_name": link_data["role_name"],
                "release_type": ReleaseType.FULL_RELEASE,
                "filename": link_data["filename"],
                "comment": None,
            }

            if release_type := link_data.get("release_type"):
                data["release_type"] = ReleaseType(release_type.title()).name

            if release_date := await cls._parse_release_date(link_data["release_date"]):
                data["release_date"] = release_date
            else:
                data["comment"] = link_data["release_date"]

            await repo.broadcasts.create(data)
            await repo.session.commit()
        except Exception as e:
            await repo.session.rollback()
            raise DatabaseError(f"Ошибка при сохранении данных: {e}") from e


class FileManager:
    """Управление операциями с файлами."""

    @staticmethod
    async def get_latest_downloaded_file(
        directory: Path, extension: str = ".crdownload"
    ) -> Optional[str]:
        """Получение последнего скачанного файла."""
        try:
            files = os.listdir(directory)

            if not files:
                return None
            latest_file = max(
                [os.path.join(directory, f) for f in files if f.endswith(extension)],
                key=os.path.getctime,
            )
            filename = os.path.basename(latest_file)
            return filename.removesuffix(extension)
        except Exception as e:
            raise FileManagerError(f"Ошибка получения файла: {e}") from e

    @classmethod
    async def wait_for_downloads(cls, timeout: int = DOWNLOAD_WAIT_TIMEOUT) -> None:
        """Ожидание завершения загрузки файлов с прогресс-баром."""
        start_time = datetime.now()
        with tqdm(
            total=timeout,
            desc="Ожидание загрузок",
            unit="s",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} сек.",
        ) as pbar:
            while any(f.endswith(".crdownload") for f in os.listdir(BROADCASTS_DIR)):
                if (datetime.now() - start_time).seconds > timeout:
                    raise DownloadTimeoutError("Превышено время ожидания загрузки")
                await asyncio.sleep(1)
                pbar.update(1)



class PageParser:
    """Парсинг страницы и обработка всех ссылок."""

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.wait = WebDriverWait(driver, DRIVER_TIMEOUT)
        self.progress_bar: Optional[tqdm] = None

    async def _click_show_roles(self) -> None:
        """Клик по кнопке показа ролей."""
        show_roles_button = self.wait.until(
            EC.element_to_be_clickable((By.NAME, "show"))
        )
        show_roles_button.click()

    async def _get_all_links(self) -> list[WebElement]:
        """Получение всех ссылок в форме."""
        form_release = self.wait.until(EC.presence_of_element_located((By.ID, "list")))
        return form_release.find_elements(By.TAG_NAME, "a")

    async def _process_single_link(self, link, repo: RequestsRepo) -> None:
        """Обработка одной ссылки."""
        link_text = link.text.strip()
        try:
            link_data = await LinkProcessor.process_link(link_text)
            if not link_data:
                return

            await self._download_file(link.get_attribute("href"))

            if filename := await FileManager.get_latest_downloaded_file(BROADCASTS_DIR):
                link_data["filename"] = filename
                await DatabaseManager.save_broadcast_data(link_data, repo)

        except Exception as e:
            logger.error(f"Ошибка обработки ссылки {link_text}: {e}")

    async def parse_page(self) -> None:
        """Основной метод парсинга страницы с прогресс-баром."""
        try:
            self.driver.get(START_URL)
            await self._click_show_roles()

            async with async_session_pool() as session:
                repo = RequestsRepo(session)
                links = await self._get_all_links()

                # Инициализация прогресс-бара
                self.progress_bar = tqdm_asyncio(
                    total=len(links),
                    desc="Обработка ссылок",
                    unit="ссылка",
                    colour="GREEN",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                )
                count = 0
                for link in links:
                    await self._process_single_link(link, repo)
                    self.progress_bar.update(1)
                    await asyncio.sleep(PAUSE_DURATION_SECONDS)
                    count += 1
                    if count == 5:
                        break

        except Exception as e:
            raise PageParsingError(f"Ошибка парсинга: {e}") from e
        finally:
            if self.progress_bar:
                self.progress_bar.close()

    async def _download_file(self, url: str) -> None:
        """Загрузка файла по ссылке."""
        try:
            original_window = self.driver.current_window_handle
            self.driver.switch_to.new_window("tab")
            self.driver.get(url)

            code_element = self.wait.until(
                EC.presence_of_element_located((By.ID, "nekto"))
            )
            input_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "code"))
            )

            input_field.send_keys(f"{code_element.text}{Keys.ENTER}")
            await asyncio.sleep(PAUSE_DURATION_SECONDS)
            self.driver.close()
            self.driver.switch_to.window(original_window)
        except Exception as e:
            raise PageParsingError(f"Ошибка загрузки файла: {e}") from e


async def run_parser() -> None:
    """Основная функция для запуска парсера."""
    try:
        async with WebDriverManager() as driver:
            parser = PageParser(driver)
            await parser.parse_page()
            await FileManager.wait_for_downloads()

    except (
        WebDriverError,
        LinkProcessingError,
        DatabaseError,
        FileManagerError,
        PageParsingError,
        DownloadTimeoutError,
    ) as e:
        logger.error(f"{e.__class__.__name__}: {e}")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка: {e}")
