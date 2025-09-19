# helpers/get_current_user.py
from fastapi import Request

async def get_current_user(request: Request):
    user = getattr(request.state, "user", None)
    return user
