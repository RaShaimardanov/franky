from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.database.repo.requests import RequestsRepo


def create_engine(
    url: str, echo: bool = False, pool_timeout: int = 1, pool_size: int = 10
) -> AsyncEngine:
    """
    Создает и возвращает асинхронный движок SQLAlchemy.

    :param url: URI для подключения к базе данных
    :param echo: Логирование запросов SQL
    :param pool_timeout: Время ожидания свободного подключения в пуле
    :param pool_size: Размер пула подключений
    :return: Асинхронный движок SQLAlchemy
    """
    return create_async_engine(
        url=url,
        echo=echo,
        # future=True,
        # pool_pre_ping=True,
        # pool_timeout=pool_timeout,
        # pool_size=pool_size,
    )


def get_async_session_maker(engine: AsyncEngine):
    """
    Создает и возвращает фабрику асинхронных сессий.

    :param engine: Асинхронный движок SQLAlchemy
    :return: Фабрика асинхронных сессий
    """
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


# Инициализация движка и фабрики сессий
engine: AsyncEngine = create_engine(url=settings.DB_URI)

async_session_pool = get_async_session_maker(engine)


async def get_repo():
    async with async_session_pool() as session:
        yield RequestsRepo(session)
