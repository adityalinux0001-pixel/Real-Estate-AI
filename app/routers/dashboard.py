from typing import Dict
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.building import Building
from app.models.file import File
from app.models.session import ChatSession
from app.schemas.dashboard import DashboardSummary
from app.core.categories import ALL_CATEGORIES
from app.models.user import User
from app.core.security import check_subscription

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    
    total_buildings = (await db.execute(select(func.count()).select_from(Building).filter(Building.user_id == current_user.id))).scalar_one()
    total_documents = (await db.execute(select(func.count()).select_from(File).filter(File.user_id == current_user.id))).scalar_one()
    total_sessions = (await db.execute(select(func.count()).select_from(ChatSession).filter(ChatSession.user_id == current_user.id))).scalar_one()
    
    result = await db.execute(
        select(File).filter(File.user_id == current_user.id).order_by(File.uploaded_at.desc()).limit(10)
    )
    recent_documents = result.scalars().all()
    
    result = await db.execute(
        select(File.category, func.count(File.id))
        .filter(File.user_id == current_user.id)
        .group_by(File.category)
    )
    file_counts = result.all()

    counts_dict = {category: count for category, count in file_counts}

    files_per_category: Dict[str, int] = {
        category: counts_dict.get(category, 0) for category in ALL_CATEGORIES
    }
    
    return DashboardSummary(
        total_buildings=total_buildings,
        total_documents=total_documents,
        total_sessions=total_sessions,
        files_per_category=files_per_category,
        recent_documents=recent_documents
    )
