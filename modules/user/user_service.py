# services/user_service.py
from typing import List, Optional
from .user_repository import UserRepository
from .user_model import User
from .dtos import CreateUserDTO, UpdateUserDTO


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, dto: CreateUserDTO) -> User:
        return await self.user_repo.create_user(dto)

    async def get_user(self, user_id: int) -> Optional[User]:
        return await self.user_repo.get_user_by_id(user_id)

    async def get_all_users(self) -> List[User]:
        return await self.user_repo.get_all_users()

    async def update_user(self, user_id: int, dto: UpdateUserDTO) -> Optional[User]:
        return await self.user_repo.update_user(user_id, dto)

    async def delete_user(self, user_id: int) -> bool:
        return await self.user_repo.delete_user(user_id)

    async def get_user_by_username(self,username:str)->Optional[User]:
        return await self.user_repo.get_user_by_username(username)