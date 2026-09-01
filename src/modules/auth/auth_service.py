from datetime import datetime, timedelta, timezone
import jwt
from modules.auth.dtos import LoginDTO,SignupDTO
from modules.user import UserService
from utils import HttpError
from modules.common.services.config_service import config_service
from modules.user.dtos import CreateUserDTO, UserPublicDTO
from utils.security import verify_password

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
    
    if not verify_password(body.password, user.password):
      raise HttpError("Password does not match", 404)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = self.create_access_token(
        data={"username": user.username,"id":user.id}, expires_delta=access_token_expires
    )

    return {"user": UserPublicDTO.model_validate(user), "accessToken": access_token}

  async def register(self, body: SignupDTO):
    # Check if user exists
    user = await self.user_service.get_user_by_username(body.username)
    if user:
        raise HttpError("User with this user name already exists", 429)

    # UserService hashes the password, so pass it through as-is.
    user = await self.user_service.create_user(
        CreateUserDTO(username=body.username, password=body.password)
    )

    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = self.create_access_token(
        data={"username": body.username,"id":user.id}, expires_delta=access_token_expires
    )

    return {"user": UserPublicDTO.model_validate(user), "accessToken": access_token}


  
  def create_access_token(self,data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
