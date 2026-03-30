from typing import List
from app.core.categories import INSIDE_CATEGORIES
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.future import select
from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.core.security import check_subscription
from app.models.user import User
from app.models.building import Building
from app.models.file import File
from app.schemas.building import BuildingCreate, BuildingResponse, BuildingUpdate
from app.services.building.utils import (
    serialize_buildings_with_count,
    serialize_building_with_count
)
from app.services.building.service import (
    get_buildings_with_file_count,
    get_building_with_file_count
)
from app.services.file.service import clear_file


router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.post("/create", response_model=BuildingResponse)
async def create_building(
    building: BuildingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await check_subscription(current_user, db)

    if building.category and building.category not in INSIDE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid building category")

    result = await db.execute(
        select(Building).filter(
            Building.address == building.address,
            Building.user_id == current_user.id,
            Building.category == building.category,
        )
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Building already created with this address")

    new_building = Building(**building.dict(), user_id=current_user.id)
    db.add(new_building)
    await db.commit()
    await db.refresh(new_building)

    return BuildingResponse(
        id=new_building.id,
        user_id=new_building.user_id,
        address=new_building.address,
        category=new_building.category,
        file_count=0,
    )


@router.get("/list", response_model=List[BuildingResponse])
async def read_buildings(category: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    rows = await get_buildings_with_file_count(db, category, current_user.id)
    return serialize_buildings_with_count(rows)


@router.get("/{building_id}", response_model=BuildingResponse)
async def read_building(building_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    row = await get_building_with_file_count(db, building_id, current_user.id)
    if not row:
        raise HTTPException(status_code=404, detail="Building not found")
    return serialize_building_with_count(row)


@router.put("/{building_id}", response_model=BuildingResponse)
async def update_building(
    building_id: int,
    building_update: BuildingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await check_subscription(current_user, db)

    result = await db.execute(
        select(Building).filter(
            Building.id == building_id,
            Building.user_id == current_user.id,
        )
    )
    building = result.scalars().first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    for key, value in building_update.dict(exclude_unset=True).items():
        setattr(building, key, value)

    await db.commit()
    await db.refresh(building)

    row = await get_building_with_file_count(db, building.id, current_user.id)
    return serialize_building_with_count(row)


@router.delete("/{building_id}")
async def delete_building(building_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    result = await db.execute(select(Building).filter(Building.id == building_id, Building.user_id == current_user.id))
    building = result.scalars().first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    files = await db.execute(select(File).filter(File.building_id == building_id, File.user_id == current_user.id))
    for file in files.scalars().all():
        await clear_file(file.id, file.path)
        
    await db.delete(building)
    await db.commit()
    
    return {"message": f"Building and its files were deleted successfully."}