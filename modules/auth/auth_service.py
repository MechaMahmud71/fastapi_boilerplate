from datetime import datetime, timedelta, timezone
import jwt
from modules.auth.dtos import LoginDTO,SignupDTO
from modules.user import UserService
from utils import HttpError
from passlib.context import CryptContext
from utils.config_service import config_service

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = config_service.get("JWT_SECRET")# use env variable in real app
ALGORITHM = config_service.get("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(config_service.get("JWT_EXPIRE_TIME")) 
class AuthService:

  def __init__(self,user_service:UserService):
    self.user_service=user_service

  async def login(self,body:LoginDTO):
    user = await self.user_service.get_user_by_username(body.username)
  
    if not user:
        raise HttpError("User not found",404)
    
    if not pwd_context.verify(body.password, user.password):
      raise HttpError("Password does not match", 404)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = self.create_access_token(
        data={"username": user.username,"id":user.id}, expires_delta=access_token_expires
    )

    return {
        "message": "Successfully logged in",
        "data": {
            "user": user,
            "access_token": access_token
        }
    }

  async def register(self, body: SignupDTO):
    # Check if user exists
    user = await self.user_service.get_user_by_username(body.username)
    if user:
        raise HttpError("User with this user name already exists", 429)

    # Hash password (sync, do NOT await)
    hashed_password = pwd_context.hash(body.password)

    # Create user
    user = await self.user_service.create_user({
        "username": body.username,
        "password": hashed_password
    })

    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = self.create_access_token(
        data={"username": body.username,"id":user.id}, expires_delta=access_token_expires
    )

    return {
        "message": "Successfully registered a user",
        "data": {
            "user": user,
            "access_token": access_token
        }
    }


  
  def create_access_token(self,data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
