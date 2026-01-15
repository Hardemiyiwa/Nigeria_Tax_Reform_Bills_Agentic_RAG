from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List, Dict, Any
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
    sources: Optional[List[Dict[str, Any]]] = None


class MessageOut(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime
    sources: Optional[List[Dict[str, Any]]] = None

    class Config:
        orm_mode = True


class ChatOut(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    messages: List[MessageOut] = []

    class Config:
        orm_mode = True


class TaxCalculatorRequest(BaseModel):
    """Request for tax scenario calculation"""
    gross_income: Optional[float] = None
    purchase_amount: Optional[float] = None
    tax_type: str = "vat"  # vat, income_tax, cit, etc.
    
    class Config:
        json_schema_extra = {
            "example": {
                "gross_income": 500000,
                "purchase_amount": 100000,
                "tax_type": "vat"
            }
        }


class TaxCalculatorResponse(BaseModel):
    """Response from tax calculator"""
    tax_type: str
    gross_amount: float
    tax_amount: float
    net_amount: float
    tax_rate: float
    description: str


class ChatExportRequest(BaseModel):
    """Request to export chat as PDF"""
    chat_id: int
    format: str = "pdf"  # pdf or json
