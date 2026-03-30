from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.file import File
from app.models.user import User
from app.schemas.file import FileResponse
from app.services.file_processing import extract_text
from app.services.file.service import save_file_to_db
from app.services.ai.smart_chunker import process_and_store_universal
from app.utils.helpers import validate_category, save_file
from app.services.file.service import clear_file
from app.core.security import check_subscription
from pathlib import Path
import logging

router = APIRouter(prefix="/files", tags=["files"])
logger = logging.getLogger(__name__)
UPLOAD_DIR = Path("uploads")


@router.post("/{category}", response_model=FileResponse)
async def upload_file(
    category: str,
    file: UploadFile = FastAPIFile(...),
    building_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, building_id, current_user, db)
    await check_subscription(current_user, db)

    if building_id is not None:
        dir_path = UPLOAD_DIR / str(building_id) / category
    else:
        dir_path = UPLOAD_DIR / "outer" / category
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path, original_name = await save_file(dir_path, file)

    db_file = await save_file_to_db(
        name=original_name,
        path=file_path,
        category=category,
        building_id=building_id,
        user_id=current_user.id,
        db=db
    )

    try:
        text = await extract_text(file_path)
        logger.info(f"Extracted text length: {len(text)}")

        num_chunks = await process_and_store_universal(
            text=text,
            filename=file.filename,
            user_id=current_user.id,
            category=category,
            file_id=db_file.id,
            building_id=building_id,
        )
        
        logger.info(f"Uploaded file {db_file.id} with {num_chunks} chunks.")
        
    except Exception as e:
        try:
            success = await clear_file(db_file.id, db_file.path)
            if not success:
                logger.error(f"Failed to clear vectors and file for file ID {db_file.id}")
        except Exception as e:
            logger.error(f"Error during cleanup after failed upload: {e}")
            
        await db.delete(db_file)
        await db.commit()
        logger.exception(f"Error occurred while processing the file: {e}")
        raise HTTPException(status_code=400, detail="Error occurred while processing the file")

    return db_file


@router.get("/{category}", response_model=List[FileResponse])
async def read_files(
    category: str,
    building_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, building_id, current_user, db)
    await check_subscription(current_user, db)

    query = select(File).filter(File.category == category, File.user_id == current_user.id)
    if building_id is not None:
        query = query.filter(File.building_id == building_id)
    else:
        query = query.filter(File.building_id == None)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{category}/{file_id}", response_model=FileResponse)
async def read_file(
    category: str,
    file_id: int,
    building_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, building_id, current_user, db)
    await check_subscription(current_user, db)

    query = select(File).filter(File.id == file_id, File.category == category, File.user_id == current_user.id)
    if building_id is not None:
        query = query.filter(File.building_id == building_id)
    else:
        query = query.filter(File.building_id == None)

    result = await db.execute(query)
    file = result.scalars().first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.put("/{category}/{file_id}", response_model=FileResponse)
async def update_file(
    category: str,
    file_id: int,
    file: UploadFile = FastAPIFile(...),
    building_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, building_id, current_user, db)
    await check_subscription(current_user, db)

    query = select(File).filter(
        File.id == file_id,
        File.category == category,
        File.user_id == current_user.id
    )
    if building_id is not None:
        query = query.filter(File.building_id == building_id)
    else:
        query = query.filter(File.building_id == None)

    result = await db.execute(query)
    db_file = result.scalars().first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    success = await clear_file(db_file.id, db_file.path)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear old vectors and file")

    if building_id is not None:
        dir_path = UPLOAD_DIR / str(building_id) / category
    else:
        dir_path = UPLOAD_DIR / "outer" / category
    
    dir_path.mkdir(parents=True, exist_ok=True)

    new_path, original_name = await save_file(dir_path, file)

    db_file.filename = original_name
    db_file.path = new_path

    try:
        text = await extract_text(new_path)

        num_chunks = await process_and_store_universal(
            text=text,
            filename=file.filename,
            user_id=current_user.id,
            category=category,
            file_id=db_file.id,
            building_id=building_id,
        )
        
        logger.info(f"Updated file {db_file.id} with {num_chunks} chunks.")
        
        await db.commit()
        await db.refresh(db_file)
    except Exception as e:
        try:
            success = await clear_file(db_file.id, db_file.path)
            if not success:
                logger.error(f"Failed to clear vectors and file for file ID {db_file.id}")
        except Exception as e:
            logger.error(f"Error during cleanup after failed upload: {e}")
        
        await db.rollback()
        logger.error(f"Error in vectorizing the data: {e}")
        raise HTTPException(status_code=500, detail="Error updating file")

    return db_file


@router.delete("/{category}/{file_id}")
async def delete_file(
    category: str,
    file_id: int,
    building_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, building_id, current_user, db)
    await check_subscription(current_user, db)

    query = select(File).filter(File.id == file_id, File.category == category, File.user_id == current_user.id)
    if building_id is not None:
        query = query.filter(File.building_id == building_id)
    else:
        query = query.filter(File.building_id == None)

    result = await db.execute(query)
    file = result.scalars().first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    success = await clear_file(file.id, file.path)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear vectors and file")

    await db.delete(file)
    await db.commit()
    return {"message": "File deleted successfully"}
