from datetime import date

from sqlalchemy import String, Date, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.utils.enums import ReleaseType


class Broadcast(Base):
    role_name: Mapped[str] = mapped_column(String(128), nullable=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=True)
    release_type: Mapped[str] = mapped_column(Enum(ReleaseType), nullable=True)
    comment: Mapped[str] = mapped_column(String(128), nullable=True)
    filename: Mapped[str] = mapped_column(String(128), nullable=True)
    telegram_file_id: Mapped[str] = mapped_column(
        String(128), nullable=True
    )
    telegram_file_id_alt: Mapped[str] = mapped_column(
        String(128), nullable=True
    )

    # кто добавил этот выпуск в избранное
    favourites: Mapped[list["Favourite"]] = relationship(
        back_populates="broadcast", cascade="all, delete-orphan"
    )

