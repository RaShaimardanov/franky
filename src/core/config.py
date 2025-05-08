from typing import Optional

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class TelegramBotSettings(BaseConfig):
    TOKEN: str
    PARSE_MODE: str = "HTML"
    ADMIN_CHAT_ID: int


class Settings(BaseConfig):
    TELEGRAM: TelegramBotSettings = Field(default_factory=TelegramBotSettings)
    DB_URI: str =  "sqlite+aiosqlite:///database.sqlite3"

settings = Settings()
