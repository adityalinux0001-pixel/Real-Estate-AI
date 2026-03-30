from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse
from app.utils.helpers import save_file
from app.core.security import check_subscription

router = APIRouter(prefix="/users", tags=["users"])
UPLOAD_DIR = Path("uploads")


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .filter(User.id == current_user.id)
        .options(selectinload(User.subscription))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # await check_subscription(user, db)
    return user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    company_name: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    company_address: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    zip_code: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    banner_photo: Optional[UploadFile] = File(None),
    photo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await check_subscription(current_user, db)
    user_data = {
        "company_name": company_name,
        "contact_person": contact_person,
        "company_address": company_address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "phone_number": phone_number,
    }
    
    for field, value in user_data.items():
        if value is not None:
            setattr(current_user, field, value)

    user_dir = UPLOAD_DIR / "users" / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    if photo:
        if current_user.photo:
            old_photo_path = Path(current_user.photo)
            if old_photo_path.exists():
                try:
                    old_photo_path.unlink()
                except Exception as e:
                    raise HTTPException(
                        status_code=500, detail=f"Failed to delete old photo: {str(e)}"
                    )
        photo_path, _ = await save_file(user_dir, photo)
        current_user.photo = photo_path
    
    if banner_photo:
        if current_user.banner_photo:
            old_photo_path = Path(current_user.banner_photo)
            if old_photo_path.exists():
                try:
                    old_photo_path.unlink()
                except Exception as e:
                    raise HTTPException(
                        status_code=500, detail=f"Failed to delete old banner photo: {str(e)}"
                    )
        banner_photo_path, _ = await save_file(user_dir, banner_photo)
        current_user.banner_photo = banner_photo_path

    await db.commit()
    
    result = await db.execute(
        select(User)
        .filter(User.id == current_user.id)
        .options(selectinload(User.subscription))
    )
    updated_user = result.scalars().first()
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return updated_user
