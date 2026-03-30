from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.building import Building
from app.models.file import File

async def get_buildings_with_file_count(db: AsyncSession, category: Optional[str] = None, user_id: Optional[int] = None) -> List[Tuple[Building, int]]:
    stmt = (
        select(Building, func.count(File.id).label("file_count"))
        .join(File, File.building_id == Building.id, isouter=True)
        .group_by(Building.id)
    )

    if user_id is not None:
        stmt = stmt.where(Building.user_id == user_id)
        
    if category is not None:
        stmt = stmt.where(Building.category == category)

    result = await db.execute(stmt)
    return result.all()


async def get_building_with_file_count(db: AsyncSession, building_id: int, user_id: Optional[int] = None) -> Optional[Tuple[Building, int]]:
    stmt = (
        select(Building, func.count(File.id).label("file_count"))
        .join(File, File.building_id == Building.id, isouter=True)
        .where(Building.id == building_id)
        .group_by(Building.id)
    )

    if user_id is not None:
        stmt = stmt.where(Building.user_id == user_id)

    result = await db.execute(stmt)
    return result.first()

