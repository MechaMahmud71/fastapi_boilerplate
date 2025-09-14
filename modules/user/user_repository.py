from sqlalchemy.orm import Session
from .user_model import User
from typing import List, Optional
from modules.user.dtos import CreateUserDTO, UpdateUserDTO


class UserRepository:
    def __init__(self, db_factory):
        """
        db_factory: SQLAlchemy sessionmaker
        """
        self.db_factory = db_factory

    def create_user(self, dto: CreateUserDTO) -> User:
        with self.db_factory() as session:
            new_user = User(**dto.dict())
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            return new_user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        with self.db_factory() as session:
            return session.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        with self.db_factory() as session:
            return session.query(User).filter(User.email == email).first()

    def get_all_users(self) -> List[User]:
        with self.db_factory() as session:
            return session.query(User).all()

    def update_user(self, user_id: int, dto: UpdateUserDTO) -> Optional[User]:
        with self.db_factory() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            update_data = dto.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(user, key, value)

            session.commit()
            session.refresh(user)
            return user

    def delete_user(self, user_id: int) -> bool:
        with self.db_factory() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            session.delete(user)
            session.commit()
            return True
