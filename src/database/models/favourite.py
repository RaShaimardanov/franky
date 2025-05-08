from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class Favourite(Base):
    """Модель Избранное: пользователь ↔ выпуск."""

    __table_args__ = (
        UniqueConstraint("user_id", "broadcast_id", name="uq_favourite_user_broadcast"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(ForeignKey("broadcasts.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())

    # отношения для навигации
    user: Mapped["User"] = relationship(back_populates="favourites")
    broadcast: Mapped["Broadcast"] = relationship(back_populates="favourites")