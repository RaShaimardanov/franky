from typing import Optional

from sqlalchemy.dialects.postgresql import insert

from src.database.models.user import User
from src.database.repo.base import BaseRepo


class UserRepo(BaseRepo):

    async def get_or_create_user(self, **kwargs) -> Optional[User]:
        """
        Создает или обновляет нового пользователя в базе данных
        и возвращает объект User.
        """
        insert_stmt = (
            insert(User)
            .values(**kwargs)
            .on_conflict_do_update(
                index_elements=[User.telegram_id],
                set_=kwargs,
            )
            .returning(User)
        )
        result = await self.session.execute(insert_stmt)

        await self.session.commit()
        return result.scalar_one_or_none()
