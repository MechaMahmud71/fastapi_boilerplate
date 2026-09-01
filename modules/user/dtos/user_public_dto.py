from pydantic import BaseModel, ConfigDict


class UserPublicDTO(BaseModel):
    """A user as it leaves the API — never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
