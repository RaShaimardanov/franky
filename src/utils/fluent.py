from pathlib import Path
from typing import Optional

from fluent_compiler.bundle import FluentBundle
from fluentogram import FluentTranslator, TranslatorHub

from src.core.paths import LOCALES_DIR


class TranslationLoader:
    """
    Отвечает за загрузку содержимого файлов переводов.

    :param locales_folder: Путь к директории, содержащей файлы с переводами.
    """

    def __init__(self, locales_folder: Path):
        self.locales_folder = locales_folder

    def get_content(self, locale: str) -> Optional[str]:
        """Метод для получения содержимого файла перевода для заданного языка."""
        with open(self.locales_folder / f"{locale}.ftl", "r", encoding="utf-8") as f:
            return f.read()


class FluentService:
    """Предоставляет интерфейс для работы с переводами через TranslatorHub."""

    def __init__(self, loader, locales_map):
        self._hub: Optional[TranslatorHub] = None
        self.loader = loader
        self.locales_map = locales_map

    @property
    def hub(self):
        """
        Свойство, возвращающее объект TranslatorHub.
        Если TranslatorHub ещё не был инициализирован, он создаётся с указанными настройками.
        """
        if not self._hub:
            self._hub = TranslatorHub(
                self.locales_map,
                translators=[
                    FluentTranslator(
                        locale="ru",
                        translator=FluentBundle.from_string(
                            "ru-RU",
                            self.loader.get_content("ru"),
                            use_isolating=False,
                        ),
                    ),
                ],
                root_locale="ru",
            )
        return self._hub

    def get_translator_by_locale(self, locale):
        """Метод для получения переводчика для заданного языка."""
        if locale not in self.locales_map:
            return self.hub.get_translator_by_locale(self.hub.root_locale)
        return self.hub.get_translator_by_locale(locale)


def configure_fluent():
    """Функция для конфигурации и создания экземпляра FluentService."""
    locales_map = {
        "ru": ("ru",),
    }
    loader = TranslationLoader(
        LOCALES_DIR,
    )
    return FluentService(loader, locales_map)
