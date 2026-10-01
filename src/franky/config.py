from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseModel):
    token: SecretStr
    # Чат (канал/группа/личка админа), куда заранее заливаются аудио, чтобы получить file_id.
    storage_chat_id: int | None = None
    admin_ids: list[int] = Field(default_factory=list)
    # Свой Bot API сервер (telegram-bot-api) снимает лимит 50 МБ на загрузку файлов.
    api_server: str | None = None


class DatabaseSettings(BaseModel):
    dsn: PostgresDsn = PostgresDsn("postgresql+asyncpg://franky:franky@localhost:5432/franky")
    echo: bool = False


class CatalogSettings(BaseModel):
    base_url: str = "http://fshow.info/"
    audio_dir: Path = Path("data/audio")
    request_delay: float = 2.0  # вежливая пауза между запросами к сайту, сек.


class GameSettings(BaseModel):
    max_attempts: int = 3
    max_hints: int = 2


# env_ignore_empty: пустая переменная (Coolify передаёт незаполненные как "") = не задана.
_ENV_CONFIG = SettingsConfigDict(
    env_file=".env", env_nested_delimiter="__", env_ignore_empty=True, extra="ignore"
)


class Settings(BaseSettings):
    model_config = _ENV_CONFIG

    bot: BotSettings
    db: DatabaseSettings = DatabaseSettings()
    catalog: CatalogSettings = CatalogSettings()
    game: GameSettings = GameSettings()
    log_level: str = "INFO"
    log_json: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # поля заполняются из окружения и .env


class _DatabaseOnly(BaseSettings):
    model_config = _ENV_CONFIG
    db: DatabaseSettings = DatabaseSettings()


def get_database_settings() -> DatabaseSettings:
    """Только настройки БД — для миграций, которым токен бота не нужен."""
    return _DatabaseOnly().db
