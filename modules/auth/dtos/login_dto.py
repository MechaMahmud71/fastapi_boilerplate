from pydantic import BaseModel,Field

class LoginDTO(BaseModel):
  username:str=Field("Faruk")
  password:str