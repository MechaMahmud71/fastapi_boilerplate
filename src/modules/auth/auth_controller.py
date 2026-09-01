from fastapi import APIRouter,Depends
from .auth_service import AuthService
from src.modules.auth.dtos.login_dto import LoginDTO
from src.modules.auth.dtos.signup_dto import SignupDTO

class AuthController:
  def __init__(self,auth_service:AuthService):
    self.router=APIRouter(prefix="/auth",tags=["Public Auth"])
    self.__add_routes()
    self.auth_service=auth_service

  def __add_routes(self):
    
    @self.router.post("/login")
    async def login(body:LoginDTO):
      return await self.auth_service.login(body)
    
    @self.router.post("/register")
    async def register(body:SignupDTO):
      return await self.auth_service.register(body)
