import asyncio
import json
import random
import re
import string
import tempfile
import os
from typing import Any
from fastapi import HTTPException, UploadFile
from app.core.categories import INSIDE_CATEGORIES, OUTER_CATEGORIES
from app.models.building import Building
from app.models.session import ChatSession
from app.models.subscription import Subscription
from app.models.user import User
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4
from pathlib import Path
import aiofiles
import logging
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)


async def run_stripe(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

async def get_user_subscription(current_user: User, db: AsyncSession):
    result = await db.execute(select(Subscription).filter(Subscription.user_id == current_user.id))
    subscription = result.scalars().first()
    return subscription

async def get_subscription_by_id(subscription_id: str, db: AsyncSession):
    result = await db.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
    subscription = result.scalars().first()
    return subscription

def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))

async def validate_category(category: str, building_id: int | None, current_user: User, db: AsyncSession) -> None:
    if building_id is not None and category not in INSIDE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category for building")
    if building_id is None and category not in OUTER_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")

    if building_id is not None:
        result = await db.execute(
            select(Building).filter(Building.id == building_id, Building.user_id == current_user.id)
        )
        building = result.scalars().first()
        if not building:
            raise HTTPException(status_code=404, detail="Invalid building")

async def save_file(dir_path: Path, file: UploadFile) -> tuple[str, str]:
    file_id_str = str(uuid4())
    extension = Path(file.filename).suffix
    original_name = Path(file.filename).name

    uuid_filename = f"{file_id_str}{extension}"
    file_path = dir_path / uuid_filename

    async with aiofiles.open(file_path, "wb") as buffer:
        content = await file.read()
        await buffer.write(content)
    
    await file.close()
    
    return str(file_path), original_name


async def save_to_temp(file) -> str:
    temp_path = os.path.join(tempfile.gettempdir(), file.filename)
    async with aiofiles.open(temp_path, "wb") as f:
        content = await file.read()
        await f.write(content)
        
    return temp_path


async def get_or_create_session(request: ChatRequest, current_user: User, db: AsyncSession):
    if request.session_id is None:
        raise HTTPException(status_code=404, detail="Invalid session ID")
    
    result = await db.execute(select(ChatSession).filter(ChatSession.id == request.session_id))
    session = result.scalars().first()
    if not session:
        session = ChatSession(
            id=request.session_id,
            user_id=current_user.id,
            building_id=request.building_id,
            category=request.category,
            title=None
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
    elif session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this session")

    return session


async def validate_pdf_upload(file: UploadFile) -> bytes:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    content = await file.read()
    if len(content) > 32 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 32 MB")

    return content


def strip_code_fence(s: str) -> str:
    return re.sub(r'```json\n?|\n?```', '', s).strip()


def safe_parse_json(text: str, default: Any = None) -> Any:
    try:
        return json.loads(text)
    except Exception as e:
        logger.warning("Failed to parse JSON from LLM response: %s. Raw: %.200s", e, text)
        return default