from fastapi import APIRouter,Depends
from .auth_service import AuthService
from .dtos import LoginDTO,SignupDTO

class AuthController:
  def __init__(self):
    self.router=APIRouter(prefix="/auth",tags=["Public Auth"])
    self.__add_routes()

  def __add_routes(self):
    
    @self.router.post("/login")
    def login(body:LoginDTO,service:AuthService=Depends()):
      return service.login(body)
    
    @self.router.post("/register")
    def register(body:SignupDTO,service:AuthService=Depends()):
      return body