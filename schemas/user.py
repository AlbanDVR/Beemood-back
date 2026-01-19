from pydantic import BaseModel
from typing import Optional
from datetime import date

class UserBase(BaseModel):
    access_code : str

class LoginResponse(BaseModel):
    display_name: str
    email: str
    session_token: str
    external_urls: dict
    images: list[dict]
    joined: date
    user_id: str