# modules/user/user_controller.py
from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPBearer

from helpers.get_current_user import get_current_user
from modules.common.decorators import Protected
from .user_service import UserService
from .dtos import CreateUserDTO, UpdateUserDTO

# Tell Swagger UI to expect `Authorization: Bearer <token>`
bearer_scheme = HTTPBearer()
class UserController:
    def __init__(self, user_service: UserService):
        self.user_service = user_service
        self.router = APIRouter(prefix="/users", tags=["Users"])
        self.__add_routes()

    def __add_routes(self):
        @self.router.post("/")
        async def create_user(body: CreateUserDTO):
            return await self.user_service.create_user(body)


        @self.router.get("/")
        async def get_all_users():
            return await self.user_service.get_all_users()
        
        @self.router.get("/me",dependencies=[Security(bearer_scheme)])
        @Protected
        async def getCurrentUser(request:Request):
            return await get_current_user(request)

        @self.router.get("/{user_id}")
        async def get_user(user_id: int):
            return await self.user_service.get_user(user_id)
            

        @self.router.put("/{user_id}")
        async def update_user(user_id: int, body: UpdateUserDTO):
            return await self.user_service.update_user(user_id, body)


        @self.router.delete("/{user_id}")
        async def delete_user(user_id: int):
            return await self.user_service.delete_user(user_id)
        