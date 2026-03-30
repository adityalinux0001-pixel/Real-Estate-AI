from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatSessionBase(BaseModel):
    title: Optional[str] = None

class ChatSessionCreate(ChatSessionBase):
    building_id: Optional[int] = None
    category: str

class ChatSessionResponse(ChatSessionBase):
    id: str
    user_id: int
    building_id: Optional[int] = None
    category: str
    created_at: datetime

    class Config:
        from_attributes = True