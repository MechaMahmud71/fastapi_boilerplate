from typing import Optional

from pydantic import BaseModel, Field


class CreateTodoDTO(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    completed: bool = False
