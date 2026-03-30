from typing import Dict, List
from pydantic import BaseModel
from app.schemas.file import FileResponse


class DashboardSummary(BaseModel):
    total_buildings: int
    total_documents: int
    total_sessions: int
    files_per_category: Dict[str, int]
    recent_documents: List[FileResponse]