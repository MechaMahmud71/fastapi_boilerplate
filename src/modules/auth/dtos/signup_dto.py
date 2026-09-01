from pydantic import BaseModel, EmailStr, Field

class SignupDTO(BaseModel):
  username:str=Field(...,min_length=3,max_length=50)
  # email:EmailStr
  password:str
