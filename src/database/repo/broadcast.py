from typing import Optional

from sqlalchemy import select, func, or_

from src.database.models.broadcast import Broadcast
from src.database.repo.base import BaseRepo


class BroadcastRepo(BaseRepo):
    async def get_random_broadcast(self) -> Optional[Broadcast]:
        """Возвращает случайный выпуск"""
        db_obj = await self.session.execute(
            select(self.model).order_by(func.random()).limit(1)
        )
        return db_obj.scalars().one_or_none()

    async def get_broadcast_by_file_id(self, file_id: str) -> Optional[Broadcast]:
        """Ищет выпуск по file_id"""
        db_obj = await self.session.execute(
            select(self.model).where(
                or_(
                    self.model.telegram_file_id == file_id,
                    self.model.telegram_file_id_alt == file_id,
                )
            )
        )
        return db_obj.scalar_one_or_none()
