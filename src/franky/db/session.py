from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from franky.config import DatabaseSettings

SessionFactory = async_sessionmaker[AsyncSession]


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(str(settings.dsn), echo=settings.echo, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    return async_sessionmaker(engine, expire_on_commit=False)
