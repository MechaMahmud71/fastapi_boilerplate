from functools import wraps
from modules.common.services import config_service
from utils import HttpError
from fastapi import Request
import jwt

def Protected(func):
  @wraps(func)
  async def wrapper(*args,request:Request,**kwargs):

    if request is None:
      raise HttpError("Request Object not found",404)
    auth_header=request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
      raise HttpError("Token not found",404)
    
    token=auth_header.split(" ")[1]

    try:
      decoded_user=jwt.decode(token,config_service.get("JWT_SECRET"),algorithms=[config_service.get("JWT_ALGORITHM")])
      request.state.user=decoded_user
      
    except jwt.ExpiredSignatureError:
            raise HttpError("Token Expired",401)
    except jwt.InvalidTokenError:
            raise HttpError("Invalid Token",401)
    
    return await func(*args,request,**kwargs)
  
  return wrapper
