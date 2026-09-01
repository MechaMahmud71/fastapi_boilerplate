from typing import Optional, Sequence

from src.utils.expection import HttpError

from src.modules.todo.dtos.create_dto import CreateTodoDTO
from src.modules.todo.dtos.update_dto import UpdateTodoDTO
from .todo_model import Todo
from .todo_repository import TodoRepository


class TodoService:
    """Todos are always scoped to their owner.

    Every lookup goes through `_owned`, which reports someone else's todo as
    404 rather than 403 — a 403 would confirm that the id exists.
    """

    def __init__(self, todo_repo: TodoRepository):
        self.todo_repo = todo_repo

    async def _owned(self, todo_id: int, user_id: int) -> Todo:
        todo = await self.todo_repo.get_todo_by_id(todo_id)
        if not todo or todo.user_id != user_id:
            raise HttpError("Todo not found", 404)
        return todo

    async def create_todo(self, user_id: int, dto: CreateTodoDTO) -> Todo:
        return await self.todo_repo.create_todo(user_id, dto)

    async def get_todo(self, todo_id: int, user_id: int) -> Todo:
        return await self._owned(todo_id, user_id)

    async def list_todos(
        self,
        user_id: int,
        completed: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        items = await self.todo_repo.get_todos_by_user(
            user_id, completed=completed, limit=limit, offset=offset
        )
        total = await self.todo_repo.count_todos_by_user(user_id, completed=completed)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def update_todo(
        self, todo_id: int, user_id: int, dto: UpdateTodoDTO
    ) -> Todo:
        await self._owned(todo_id, user_id)

        if not dto.model_dump(exclude_unset=True):
            raise HttpError("No fields to update", 400)

        return await self.todo_repo.update_todo(todo_id, dto)

    async def delete_todo(self, todo_id: int, user_id: int) -> bool:
        await self._owned(todo_id, user_id)
        return await self.todo_repo.delete_todo(todo_id)
