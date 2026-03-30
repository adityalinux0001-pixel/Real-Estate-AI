from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class FileBase(BaseModel):
    filename: str
    path: str

class FileCreate(BaseModel):
    category: str

class FileResponse(FileBase):
    id: int
    category: str
    building_id: Optional[int] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True