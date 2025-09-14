from fastapi import APIRouter
from utils.container import container

api_router = APIRouter()

# Include user controller
user_controller = container.user_controller()
api_router.include_router(user_controller.router)
