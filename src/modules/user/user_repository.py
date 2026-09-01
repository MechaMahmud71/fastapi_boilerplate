from typing import Optional, Sequence

from sqlalchemy import select

from .user_model import User
from src.modules.user.dtos import CreateUserDTO, UpdateUserDTO


class UserRepository:
    def __init__(self, db_factory):
        self.db_factory = db_factory

    async def create_user(self, dto: CreateUserDTO) -> User:
        async with self.db_factory() as db:
            new_user = User(**dto.model_dump())
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            return new_user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        async with self.db_factory() as db:
            return await db.get(User, user_id)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with self.db_factory() as db:
            return await db.scalar(select(User).where(User.email == email))

    async def get_all_users(self) -> Sequence[User]:
        async with self.db_factory() as db:
            result = await db.scalars(select(User))
            return result.all()

    async def update_user(self, user_id: int, dto: UpdateUserDTO) -> Optional[User]:
        async with self.db_factory() as db:
            user = await db.get(User, user_id)
            if not user:
                return None

            for key, value in dto.model_dump(exclude_unset=True).items():
                setattr(user, key, value)

            await db.commit()
            await db.refresh(user)
            return user

    async def delete_user(self, user_id: int) -> bool:
        async with self.db_factory() as db:
            user = await db.get(User, user_id)
            if not user:
                return False
            await db.delete(user)
            await db.commit()
            return True

    async def get_user_by_username(self, username: str) -> Optional[User]:
        async with self.db_factory() as db:
            return await db.scalar(select(User).where(User.username == username))
