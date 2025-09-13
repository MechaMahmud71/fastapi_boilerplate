from fastapi import APIRouter

from modules.auth.auth_controller import AuthController

api_router=APIRouter()

api_router.include_router(AuthController().router)