from pydantic import BaseModel

class UserBase(BaseModel):
    access_code : str