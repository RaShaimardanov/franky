import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from franky.db.models import Base

TEST_DSN = os.getenv("TEST_DB_DSN")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Сессия на чистой схеме в Postgres. Без TEST_DB_DSN интеграционные тесты пропускаются."""
    if not TEST_DSN:
        pytest.skip("TEST_DB_DSN не задан — интеграционные тесты с Postgres пропущены")
    engine = create_async_engine(TEST_DSN)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()
