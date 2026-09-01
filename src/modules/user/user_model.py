from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.utils.db_connection import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    # email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))
    # todos: Mapped[list["Todo"]] = relationship(back_populates="user")  # One-to-Many
