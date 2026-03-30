from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select
from datetime import datetime, timedelta
from app.models.user import User, OTP
from app.core.security import get_password_hash, verify_password
from app.utils.helpers import generate_otp
from app.services.auth.email import send_email
from app.schemas.user import SuperAdminCreate, UserCreate

async def signup(db: AsyncSession, user_in: UserCreate):
    result = await db.execute(select(User).filter(User.email == user_in.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    result = await db.execute(select(User).filter(User.company_name == user_in.company_name))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Company name already registered")
        
    hashed_password = get_password_hash(user_in.password)
    
    user = User(
        company_name=user_in.company_name,
        contact_person=user_in.contact_person,
        company_address=user_in.company_address,
        city=user_in.city,
        state=user_in.state,
        zip_code=user_in.zip_code,
        phone_number=user_in.phone_number,
        email=user_in.email,
        password=hashed_password,
        is_verified=False,
        is_active=True,
        is_superadmin=False
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)

    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription))
        .filter(User.id == user.id)
    )
    user = result.scalars().first()

    await send_otp(db, user.email, otp_type="verification")
    return user


async def signup_superadmin(db: AsyncSession, user_in: SuperAdminCreate):
    result = await db.execute(select(User).filter(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if user_in.company_name:
        result = await db.execute(select(User).filter(User.company_name == user_in.company_name))
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Company name already registered")
    
    hashed_password = get_password_hash(user_in.password)
    
    user = User(
        email=user_in.email,
        password=hashed_password,
        contact_person=user_in.contact_person,
        company_name=user_in.company_name or "Admin Company",
        company_address="N/A",
        zip_code="000000",
        is_active=True,
        is_verified=True,
        is_superadmin=True
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)

    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription))
        .filter(User.id == user.id)
    )
    user = result.scalars().first()

    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    result = await db.execute(
        select(User)
        .filter(User.email == email)
        .options(selectinload(User.subscription))
    )
    user = result.scalars().first()
    if not user or not verify_password(password, user.password):
        return None
    return user


async def send_otp(db: AsyncSession, email: str, otp_type: str = "verification"):
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    otp = OTP(user_id=user.id, code=otp_code, expires_at=expires_at, type=otp_type)
    db.add(otp)
    await db.commit()
    subject = "Email Verification OTP" if otp_type == "verification" else "Password Reset OTP"
    await send_email(email, subject, f"Your OTP is {otp_code}. It expires in 10 minutes.")
    return {"message": "OTP sent to email"}


async def verify_otp(db: AsyncSession, email: str, otp_code: str, otp_type: str):
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(OTP).filter(
            OTP.user_id == user.id,
            OTP.code == otp_code,
            OTP.type == otp_type,
        )
    )
    otp = result.scalars().first()

    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if otp_type == "verification":
        user.is_verified = True
        await db.delete(otp)
        await db.commit()
        return {"message": "Email verified successfully"}

    elif otp_type == "reset":
        otp.verified = True
        await db.commit()
        return {"message": "Password reset OTP verified successfully"}

    else:
        raise HTTPException(status_code=400, detail="Invalid OTP type")
        

async def update_password(db: AsyncSession, email: str, new_password: str):
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(OTP).filter(
            OTP.user_id == user.id,
            OTP.type == "reset",
            OTP.verified == True,
        )
    )
    otp = result.scalars().first()

    if not otp:
        raise HTTPException(status_code=400, detail="OTP not verified")

    user.password = get_password_hash(new_password)
    await db.delete(otp)
    await db.commit()
    return {"message": "Password reset successful"}
