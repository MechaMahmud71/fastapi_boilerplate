from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.utils.db_connection import Base

if TYPE_CHECKING:  # avoids a circular import at runtime
    from src.modules.user.user_model import User


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(String(1000), default=None)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Many-to-one: a todo belongs to exactly one user. ondelete="CASCADE" lets
    # the database remove a user's todos when the user is deleted.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user: Mapped["User"] = relationship(back_populates="todos")
