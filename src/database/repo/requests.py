from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.favourite import Favourite
from src.database.models.broadcast import Broadcast
from src.database.models.user import User
from src.database.repo.broadcast import BroadcastRepo
from src.database.repo.favourite import FavouriteRepo
from src.database.repo.user import UserRepo


@dataclass
class RequestsRepo:
    """
    Хранилище для обработки операций с базами данных.
    Этот класс содержит все хранилища для моделей баз данных.
    Вы можете добавить дополнительные хранилища в качестве свойств к этому классу,
    чтобы они были легко доступны.
    """

    session: AsyncSession

    @property
    def broadcasts(self) -> BroadcastRepo:
        return BroadcastRepo(model=Broadcast, session=self.session)

    @property
    def users(self) -> UserRepo:
        return UserRepo(model=User, session=self.session)

    @property
    def favourites(self) -> FavouriteRepo:
        return FavouriteRepo(model=Favourite, session=self.session)