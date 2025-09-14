from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from utils.db_connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    # email = Column(String, unique=True)
    password = Column(String)
    # todos = relationship("Todo", back_populates="user")  # One-to-Many