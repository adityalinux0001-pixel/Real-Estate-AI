from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.database import get_db
from app.services.auth.auth import signup, authenticate_user, send_otp, verify_otp, update_password
from app.core.security import create_access_token
from app.schemas.user import (
    ResetPasswordRequest,
    UserCreate,
    UserResponse,
    LoginRequest,
    ForgotPasswordRequest,
    VerifyOtpRequest,
)
from datetime import timedelta
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await signup(db, user)
    return db_user


@router.post("/login")
async def login_for_access_token(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified",
        )
    
    access_token_expires = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer", "is_superadmin": user.is_superadmin, "subscription": {"status": user.subscription.status} if user.subscription else None}


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await send_otp(db, request.email, otp_type="reset")


@router.post("/verify-otp")
async def verify_otp_endpoint(request: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    return await verify_otp(db, request.email, request.otp, request.type)


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await update_password(db, request.email, request.new_password)
