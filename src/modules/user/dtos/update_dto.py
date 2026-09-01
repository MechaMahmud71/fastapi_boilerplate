from pydantic import BaseModel
from typing import Optional

class UpdateUserDTO(BaseModel):
  username:Optional[str]=None
  password:Optional[str]=None
  # email:Optional[str]=None
