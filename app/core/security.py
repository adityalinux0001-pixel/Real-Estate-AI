from typing import Optional
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from app.core.config import get_settings
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException
from sqlalchemy.future import select

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

async def check_subscription(current_user: User, db: AsyncSession) -> None:
    result = await db.execute(
        select(Subscription).filter(Subscription.user_id == current_user.id)
    )
    subscription = result.scalars().first()

    if not subscription or not subscription.subscription_id:
        raise HTTPException(status_code=404, detail="You have no active subscription. Please subscribe to access this resource.")

    if subscription and subscription.status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
        raise HTTPException(status_code=403, detail="Active subscription required to access this resource")