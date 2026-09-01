from typing import Optional, Sequence

from sqlalchemy import select

from src.modules.todo.dtos.create_dto import CreateTodoDTO
from src.modules.todo.dtos.update_dto import UpdateTodoDTO

from .todo_model import Todo


class TodoRepository:
    def __init__(self, db_factory):
        self.db_factory = db_factory

    async def create_todo(self, user_id: int, dto: CreateTodoDTO) -> Todo:
        async with self.db_factory() as db:
            todo = Todo(**dto.model_dump(), user_id=user_id)
            db.add(todo)
            await db.commit()
            await db.refresh(todo)
            return todo

    async def get_todo_by_id(self, todo_id: int) -> Optional[Todo]:
        async with self.db_factory() as db:
            return await db.get(Todo, todo_id)

    async def get_todos_by_user(
        self,
        user_id: int,
        completed: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Todo]:
        async with self.db_factory() as db:
            query = select(Todo).where(Todo.user_id == user_id)
            if completed is not None:
                query = query.where(Todo.completed.is_(completed))
            query = query.order_by(Todo.id).limit(limit).offset(offset)
            result = await db.scalars(query)
            return result.all()

    async def count_todos_by_user(
        self, user_id: int, completed: Optional[bool] = None
    ) -> int:
        async with self.db_factory() as db:
            query = select(Todo).where(Todo.user_id == user_id)
            if completed is not None:
                query = query.where(Todo.completed.is_(completed))
            result = await db.scalars(query)
            return len(result.all())

    async def update_todo(self, todo_id: int, dto: UpdateTodoDTO) -> Optional[Todo]:
        async with self.db_factory() as db:
            todo = await db.get(Todo, todo_id)
            if not todo:
                return None

            for key, value in dto.model_dump(exclude_unset=True).items():
                setattr(todo, key, value)

            await db.commit()
            await db.refresh(todo)
            return todo

    async def delete_todo(self, todo_id: int) -> bool:
        async with self.db_factory() as db:
            todo = await db.get(Todo, todo_id)
            if not todo:
                return False
            await db.delete(todo)
            await db.commit()
            return True
