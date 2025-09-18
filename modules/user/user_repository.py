from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from utils.expection import HttpError
from .user_model import User
from modules.user.dtos import CreateUserDTO, UpdateUserDTO


class UserRepository:
    def __init__(self, db_factory):
        self.db_factory = db_factory

    async def create_user(self, dto: CreateUserDTO) -> User:
        async with self.db_factory() as db: 
            new_user = User(**dto)
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            return new_user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        async with self.db_factory() as db: 
            result = await db.execute(select(User).where(User.id == user_id))
            return result.scalars().first()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with self.db_factory() as db: 
            result = await db.execute(select(User).where(User.email == email))
            return result.scalars().first()

    async def get_all_users(self) -> List[User]:
        async with self.db_factory() as db: 
            result = await db.execute(select(User))
            return result.scalars().all()

    async def update_user(self, user_id: int, dto: UpdateUserDTO) -> Optional[User]:
        async with self.db_factory() as db: 
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()
            if not user:
                return None

            update_data = dto.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(user, key, value)

            await db.commit()
            await db.refresh(user)
            return user

    async def delete_user(self, user_id: int) -> bool:
        async with self.db_factory() as db: 
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()
            if not user:
                return False
            await db.delete(user)
            await db.commit()
            return True
        
    async def get_user_by_username(self,username:str)->Optional[User]:
        async with self.db_factory() as db:
            result=await db.execute(select(User).where(User.username==username))
            user=result.scalars().first()
            return user