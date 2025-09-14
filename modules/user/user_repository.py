# repositories/user_repository.py
from sqlalchemy.orm import Session
from .user_model import User
from typing import List, Optional
from modules.user.dtos import CreateUserDTO, UpdateUserDTO


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, dto: CreateUserDTO) -> User:
        new_user = User(**dto.dict())  # unpack dto into User
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_all_users(self) -> List[User]:
        return self.db.query(User).all()

    def update_user(self, user_id: int, dto: UpdateUserDTO) -> Optional[User]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        update_data = dto.dict(exclude_unset=True)  # only fields provided
        for key, value in update_data.items():
            setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        self.db.delete(user)
        self.db.commit()
        return True
