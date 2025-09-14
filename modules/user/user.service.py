# services/user_service.py
from typing import List, Optional
from .user_repository import UserRepository
from .user_model import User
from .dtos import CreateUserDTO, UpdateUserDTO


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def create_user(self, dto: CreateUserDTO) -> User:
        # Business logic: prevent duplicate emails
        existing = self.user_repo.get_user_by_email(dto.email)
        if existing:
            raise ValueError("Email already registered")
        return self.user_repo.create_user(dto.username, dto.email, dto.password)

    def get_user(self, user_id: int) -> Optional[User]:
        return self.user_repo.get_user_by_id(user_id)

    def get_all_users(self) -> List[User]:
        return self.user_repo.get_all_users()

    def update_user(self, user_id: int, dto: UpdateUserDTO) -> Optional[User]:
        return self.user_repo.update_user(
            user_id,
            dto
        )

    def delete_user(self, user_id: int) -> bool:
        return self.user_repo.delete_user(user_id)
