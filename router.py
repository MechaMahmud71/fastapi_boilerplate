from fastapi import APIRouter
from src.utils.container import container

api_router = APIRouter()

# Include user controller
user_controller = container.user_controller()
auth_controller=container.auth_controller()
todo_controller = container.todo_controller()
health_controller = container.health_controller()
api_router.include_router(user_controller.router)
api_router.include_router(auth_controller.router)
api_router.include_router(todo_controller.router)
api_router.include_router(health_controller.router)