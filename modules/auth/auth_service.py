from modules.auth.dtos import LoginDTO,SignupDTO
from utils import HttpError


class AuthService:
  def login(self,body:LoginDTO):
    if body.username=="Faruk":
      raise HttpError("Missing",500)
    return body

  def register(self,body:SignupDTO):
    return body