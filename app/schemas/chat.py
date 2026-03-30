from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    session_id: str
    query: str
    building_id: Optional[int] = None
    category: str
    file_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    