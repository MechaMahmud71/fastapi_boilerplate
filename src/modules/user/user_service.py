# services/user_service.py
from typing import Optional, Sequence

from utils import HttpError
from utils.security import hash_password

from .dtos import CreateUserDTO, UpdateUserDTO
from .user_model import User
from .user_repository import UserRepository


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, dto: CreateUserDTO) -> User:
        if await self.user_repo.get_user_by_username(dto.username):
            raise HttpError("User with this user name already exists", 409)

        # Never store a plaintext password, whichever route we were reached by.
        dto = dto.model_copy(update={"password": hash_password(dto.password)})
        return await self.user_repo.create_user(dto)

    async def get_user(self, user_id: int) -> User:
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            raise HttpError("User not found", 404)
        return user

    async def get_all_users(self) -> Sequence[User]:
        return await self.user_repo.get_all_users()

    async def update_user(self, user_id: int, dto: UpdateUserDTO) -> User:
        changes = dto.model_dump(exclude_unset=True)
        if not changes:
            raise HttpError("No fields to update", 400)

        if "username" in changes:
            existing = await self.user_repo.get_user_by_username(changes["username"])
            if existing and existing.id != user_id:
                raise HttpError("User with this user name already exists", 409)

        if "password" in changes:
            dto = dto.model_copy(update={"password": hash_password(changes["password"])})

        user = await self.user_repo.update_user(user_id, dto)
        if not user:
            raise HttpError("User not found", 404)
        return user

    async def delete_user(self, user_id: int) -> bool:
        deleted = await self.user_repo.delete_user(user_id)
        if not deleted:
            raise HttpError("User not found", 404)
        return deleted

    async def get_user_by_username(self, username: str) -> Optional[User]:
        return await self.user_repo.get_user_by_username(username)
