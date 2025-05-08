from datetime import datetime

from sqlalchemy import BIGINT, String, func, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class User(Base):
    """Модель пользователя"""

    telegram_id: Mapped[int] = mapped_column(BIGINT, unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str] = mapped_column(String(128), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(12), nullable=True)
    email: Mapped[str] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    show_role_name: Mapped[bool] = mapped_column(Boolean, default=False)

    # список объектов Favourite
    favourites: Mapped[list["Favourite"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
