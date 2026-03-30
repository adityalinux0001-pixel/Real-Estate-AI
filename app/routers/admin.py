from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select
from sqlalchemy.sql import func
from typing import Dict, List
from app.core.database import get_db
from app.dependencies import get_current_superadmin
from app.models.user import User
from app.models.building import Building
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.user import SuperAdminCreate, UserResponse
from app.schemas.building import BuildingResponse
from app.schemas.subscription import SubscriptionResponse
from app.models.session import ChatSession
from app.models.file import File
from app.services.auth.auth import signup_superadmin
from app.services.building.service import get_buildings_with_file_count
from app.services.building.utils import serialize_buildings_with_count


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/register", response_model=UserResponse)
async def create_superadmin(user: SuperAdminCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_superadmin)):
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Only superadmins can create other superadmins")

    db_user = await signup_superadmin(db, user)
    return db_user


@router.get("/analytics", response_model=Dict[str, int])
async def get_analytics(db: AsyncSession = Depends(get_db), current_superadmin: User = Depends(get_current_superadmin)):
    total_users = (await db.execute(select(func.count()).select_from(User).filter(User.is_superadmin == False))).scalar_one()
    total_admins = (await db.execute(select(func.count()).select_from(User).filter(User.is_superadmin == True))).scalar_one()
    active_subscriptions = (
        await db.execute(
            select(func.count()).select_from(Subscription).filter(Subscription.status == SubscriptionStatus.ACTIVE)
        )
    ).scalar_one()
    expired_subscriptions = (
        await db.execute(
            select(func.count()).select_from(Subscription).filter(Subscription.status == SubscriptionStatus.EXPIRED)
        )
    ).scalar_one()
    total_buildings = (await db.execute(select(func.count()).select_from(Building))).scalar_one()
    total_files = (await db.execute(select(func.count()).select_from(File))).scalar_one()
    total_chat_sessions = (await db.execute(select(func.count()).select_from(ChatSession))).scalar_one()

    return {
        "total_users": total_users,
        "total_admins": total_admins,
        "active_subscriptions": active_subscriptions,
        "expired_subscriptions": expired_subscriptions,
        "total_buildings": total_buildings,
        "total_files": total_files,
        "total_chat_sessions": total_chat_sessions
    }


@router.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), current_superadmin: User = Depends(get_current_superadmin)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription))
        .filter(User.is_superadmin == False)
    )
    users = result.scalars().all()
    return users


@router.get("/users/failed-payments", response_model=List[UserResponse])
async def list_failed_payment_users(db: AsyncSession = Depends(get_db), current_superadmin: User = Depends(get_current_superadmin)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription))
        .join(Subscription)
        .filter(Subscription.status == SubscriptionStatus.EXPIRED)
    )
    failed_users = result.scalars().all()
    return failed_users


@router.get("/buildings", response_model=List[BuildingResponse])
async def list_buildings(db: AsyncSession = Depends(get_db), current_superadmin=Depends(get_current_superadmin)):
    rows = await get_buildings_with_file_count(db)
    return serialize_buildings_with_count(rows)


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(db: AsyncSession = Depends(get_db), current_superadmin: User = Depends(get_current_superadmin)):
    result = await db.execute(select(Subscription))
    subscriptions = result.scalars().all()
    return subscriptions


@router.get("/users/{user_id}/subscription", response_model=SubscriptionResponse)
async def get_user_subscription(user_id: int, db: AsyncSession = Depends(get_db), current_superadmin: User = Depends(get_current_superadmin)):
    result = await db.execute(select(Subscription).filter(Subscription.user_id == user_id))
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription
