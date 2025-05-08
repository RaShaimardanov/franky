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


class PostgresDBSettings(BaseConfig):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_ECHO: bool = False

    POSTGRES_URI: Optional[str] = None

    @field_validator("POSTGRES_URI")
    def assemble_db_connection(
            cls, v: Optional[str], values: ValidationInfo
    ) -> str:
        if isinstance(v, str):
            return v
        # Return URL-connect 'postgresql://postgres:password@localhost:5432/postgres'
        return (
            "postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}".format(
                user=values.data["POSTGRES_USER"],
                password=values.data["POSTGRES_PASSWORD"],
                host=values.data["POSTGRES_HOST"],
                port=values.data["POSTGRES_PORT"],
                db=values.data["POSTGRES_DB"],
            )
        )
class Settings(BaseConfig):
    TELEGRAM: TelegramBotSettings = Field(default_factory=TelegramBotSettings)
    POSTGRES: PostgresDBSettings = Field(default_factory=PostgresDBSettings)
    DB_URI = "sqlite+aiosqlite:///./database.db"


settings = Settings()
