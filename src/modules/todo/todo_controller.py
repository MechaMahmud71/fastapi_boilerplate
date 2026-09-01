# src/modules/todo/todo_controller.py
from typing import List, Optional

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from src.modules.common.decorators.user_decorator import CurrentUser
from src.modules.common.decorators.protected_decorator import Protected

from src.modules.todo.dtos.create_dto import CreateTodoDTO
from src.modules.todo.dtos.todo_public_dto import TodoPublicDTO
from src.modules.todo.dtos.update_dto import UpdateTodoDTO
from .todo_service import TodoService


class TodoListDTO(BaseModel):
    """Paginated list response."""

    items: List[TodoPublicDTO]
    total: int
    limit: int
    offset: int


class TodoController:
    def __init__(self, todo_service: TodoService):
        self.todo_service = todo_service
        self.router = APIRouter(prefix="/todos", tags=["Todos"])
        self.__add_routes()

    def __add_routes(self):
        @self.router.post(
            "/",
            response_model=TodoPublicDTO,
            status_code=status.HTTP_201_CREATED,
        )
        @Protected
        async def create_todo(body: CreateTodoDTO, user: dict = CurrentUser):
            return await self.todo_service.create_todo(user["id"], body)

        @self.router.get("/", response_model=TodoListDTO)
        @Protected
        async def list_todos(
            completed: Optional[bool] = Query(
                default=None, description="Filter by completion state"
            ),
            limit: int = Query(default=50, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
            user: dict = CurrentUser,
        ):
            return await self.todo_service.list_todos(
                user["id"], completed=completed, limit=limit, offset=offset
            )

        @self.router.get("/{todo_id}", response_model=TodoPublicDTO)
        @Protected
        async def get_todo(todo_id: int, user: dict = CurrentUser):
            return await self.todo_service.get_todo(todo_id, user["id"])

        @self.router.put("/{todo_id}", response_model=TodoPublicDTO)
        @Protected
        async def update_todo(
            todo_id: int, body: UpdateTodoDTO, user: dict = CurrentUser
        ):
            return await self.todo_service.update_todo(todo_id, user["id"], body)

        @self.router.delete("/{todo_id}")
        @Protected
        async def delete_todo(todo_id: int, user: dict = CurrentUser):
            await self.todo_service.delete_todo(todo_id, user["id"])
            return {"deleted": True}
