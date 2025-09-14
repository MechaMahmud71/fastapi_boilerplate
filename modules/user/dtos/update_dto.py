from pydantic import BaseModel
from typing import Optional

class UpdateUserDTO(BaseModel):
  username:Optional[str]
  password:Optional[str]
  # email:Optional[str]
