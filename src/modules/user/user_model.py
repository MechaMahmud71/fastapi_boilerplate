from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.utils.db_connection import Base

if TYPE_CHECKING:  # avoids a circular import at runtime
    from src.modules.todo.todo_model import Todo


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    # email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))

    # One-to-many: a user has many todos. passive_deletes defers the cascade to
    # the database (ON DELETE CASCADE) instead of loading rows to delete them.
    todos: Mapped[List["Todo"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
