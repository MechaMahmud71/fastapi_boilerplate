from typing import Optional

from pydantic import BaseModel, ConfigDict


class TodoPublicDTO(BaseModel):
    """A todo as it leaves the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    user_id: int
