from typing import Optional

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from src.database.models.favourite import Favourite
from src.database.repo.base import BaseRepo


class FavouriteRepo(BaseRepo):

    async def add_favourite(
        self, *, user_id: int, broadcast_id: int
    ) -> Optional[Favourite]:
        """
        Добавляет запись «избранное».
        Благодаря composite-PK + UniqueConstraint возможен upsert-вариант
        через `ON CONFLICT DO NOTHING`, чтобы тихо игнорировать дубликаты.
        """
        stmt = (
            insert(Favourite)
            .values(user_id=user_id, broadcast_id=broadcast_id)
            .on_conflict_do_nothing()
            .returning(Favourite)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()  # None, если запись уже существовала

    async def remove_favourite(
        self, *, user_id: int, broadcast_id: int
    ) -> bool:
        """
        Удаляет запись «избранное».
        Возвращает True, если что-то действительно удалилось.
        """
        stmt = (
            delete(Favourite)
            .where(
                Favourite.user_id == user_id,
                Favourite.broadcast_id == broadcast_id,
            )
            .returning(Favourite.user_id)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none() is not None