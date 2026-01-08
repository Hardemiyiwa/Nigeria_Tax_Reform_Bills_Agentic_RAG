from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=6, max_length=256)

class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        orm_mode = True

class MessageCreate(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[int] = None

class ChatResponse(BaseModel):
    chat_id: int
    reply: str
