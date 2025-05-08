from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.user import User


class BaseRepo:
    """
    Класс, реализующий функциональность репозитория для выполнения операций с базой данных.
    """

    def __init__(self, model, session):
        self.model = model
        self.session: AsyncSession = session

    async def get(self, obj_id: int):
        db_obj = await self.session.execute(
            select(self.model).where(obj_id == self.model.id)
        )
        return db_obj.scalars().first()

    async def get_by_attribute(self, **kwargs):
        db_obj = await self.session.execute(select(self.model).filter_by(**kwargs))
        return db_obj.scalars().first()

    async def get_all(self):
        db_objs = await self.session.execute(select(self.model).order_by(self.model.id))
        return db_objs.scalars().all()

    async def create(self, data: dict, user: Optional[User] = None):
        if user is not None:
            data["user_id"] = user.id
        db_obj = self.model(**data)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, obj, update_data: dict):
        obj_data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        for field in obj_data:
            if field in update_data:
                setattr(obj, field, update_data[field])
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def remove(self, obj):
        await self.session.delete(obj)
        await self.session.commit()
        return obj
