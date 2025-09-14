# modules/user/user_controller.py
from fastapi import APIRouter, HTTPException
from .user_service import UserService
from .dtos import CreateUserDTO, UpdateUserDTO


class UserController:
    def __init__(self, user_service: UserService):
        self.user_service = user_service
        self.router = APIRouter(prefix="/users", tags=["Users"])
        self.__add_routes()

    def __add_routes(self):
        @self.router.post("/")
        def create_user(body: CreateUserDTO):
            try:
                return self.user_service.create_user(body)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.get("/")
        def get_all_users():
            return self.user_service.get_all_users()

        @self.router.get("/{user_id}")
        def get_user(user_id: int):
            user = self.user_service.get_user(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return user

        @self.router.put("/{user_id}")
        def update_user(user_id: int, body: UpdateUserDTO):
            updated_user = self.user_service.update_user(user_id, body)
            if not updated_user:
                raise HTTPException(status_code=404, detail="User not found")
            return updated_user

        @self.router.delete("/{user_id}")
        def delete_user(user_id: int):
            success = self.user_service.delete_user(user_id)
            if not success:
                raise HTTPException(status_code=404, detail="User not found")
            return {"message": "User deleted successfully"}
