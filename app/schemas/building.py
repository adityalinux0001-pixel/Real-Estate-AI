from pydantic import BaseModel
from typing import Optional


class BuildingBase(BaseModel):
    address: str
    
class BuildingCreate(BuildingBase):
    category: Optional[str] = None

class BuildingUpdate(BaseModel):
    address: Optional[str] = None

class BuildingResponse(BuildingBase):
    id: int
    user_id: int
    category: Optional[str] = None
    file_count: int
