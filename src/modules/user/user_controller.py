# modules/user/user_controller.py
from typing import List

from fastapi import APIRouter, status

from src.modules.common.decorators.user_decorator import CurrentUser
from src.modules.common.decorators.protected_decorator import Protected

from src.modules.user.dtos.create_dto import CreateUserDTO
from src.modules.user.dtos.update_dto import UpdateUserDTO
from src.modules.user.dtos.user_public_dto import UserPublicDTO
from .user_service import UserService


class UserController:
    def __init__(self, user_service: UserService):
        self.user_service = user_service
        self.router = APIRouter(prefix="/users", tags=["Users"])
        self.__add_routes()

    def __add_routes(self):
        @self.router.post(
            "/",
            response_model=UserPublicDTO,
            status_code=status.HTTP_201_CREATED,
        )
        @Protected
        async def create_user(body: CreateUserDTO):
            return await self.user_service.create_user(body)

        @self.router.get("/", response_model=List[UserPublicDTO])
        @Protected
        async def get_all_users():
            return await self.user_service.get_all_users()

        @self.router.get("/me")
        @Protected
        async def getCurrentUser(user: dict = CurrentUser):
            return user

        @self.router.get("/{user_id}", response_model=UserPublicDTO)
        @Protected
        async def get_user(user_id: int):
            return await self.user_service.get_user(user_id)

        @self.router.put("/{user_id}", response_model=UserPublicDTO)
        @Protected
        async def update_user(user_id: int, body: UpdateUserDTO):
            return await self.user_service.update_user(user_id, body)

        @self.router.delete("/{user_id}")
        @Protected
        async def delete_user(user_id: int):
            await self.user_service.delete_user(user_id)
            return {"deleted": True}
