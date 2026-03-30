import json
import os
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, Form, UploadFile, HTTPException, File as FastFile
from sqlmodel.ext.asyncio.session import AsyncSession
from app.services.ai.smart_chunker import process_and_store_universal
from app.services.file_processing import extract_text
from app.services.ai.llm import clean_and_structure_text, generate_lease_abstract, generate_lease_content, generate_pdf_summary
from app.services.file.service import clear_file, save_file_to_db, save_text_as_docx
from app.core.database import get_db
from app.core.security import check_subscription
from app.dependencies import get_current_user
from app.models.user import User
from app.utils.helpers import validate_category, save_to_temp, validate_pdf_upload
from app.schemas.file import FileResponse
from app.schemas.lease import LeaseInput
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/doc_ai", tags=["document AI"])
UPLOAD_DIR = Path("uploads")


@router.post("/cleaner", response_model=FileResponse)
async def document_cleaner(
    category: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, None, current_user, db)
    await check_subscription(current_user, db)

    dir_path = UPLOAD_DIR / "outer" / str(category)
    dir_path.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        temp_path = await save_to_temp(file)
        text = await extract_text(temp_path)

        if not text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in file.")

        structured_text = await clean_and_structure_text(text)

        file_id_str = str(uuid4())
        original_name = Path(file.filename).stem
        safe_name = f"{original_name}_structured.docx"
        file_path = dir_path / f"{file_id_str}.docx"
        
        await save_text_as_docx(structured_text, str(file_path), key="structured")

        db_file = await save_file_to_db(
            name=safe_name,
            path=file_path,
            category=category,
            building_id=None,
            user_id=current_user.id,
            db=db
        )
        return db_file

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            

@router.post("/lease_abstract", response_model=FileResponse)
async def lease_abstract(
    category: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, None, current_user, db)
    await check_subscription(current_user, db)

    dir_path = UPLOAD_DIR / "outer" / str(category)
    dir_path.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        temp_path = await save_to_temp(file)
        text = await extract_text(temp_path)

        if not text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in file.")

        generated_text = await generate_lease_abstract(text)

        file_id_str = str(uuid4())
        original_name = Path(file.filename).stem
        safe_name = f"{original_name}_ai_lease.docx"
        file_path = dir_path / f"{file_id_str}.docx"
        
        await save_text_as_docx(generated_text, str(file_path), key="lease_abstract")

        db_file = await save_file_to_db(
            name=safe_name,
            path=file_path,
            category=category,
            building_id=None,
            user_id=current_user.id,
            db=db
        )
        return db_file

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/lease-generator", response_model=FileResponse)
async def generate_lease(
    category: str,
    fields_json: str = Form(...),
    template: UploadFile = FastFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_subscription(current_user, db)
    await validate_category(category, None, current_user, db)

    dir_path = UPLOAD_DIR / "outer" / str(category)
    dir_path.mkdir(parents=True, exist_ok=True)
    temp_path = None

    try:
        try:
            fields_dict = json.loads(fields_json)
            fields = LeaseInput(**fields_dict)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid fields JSON: {str(e)}")
        
        temp_path = await save_to_temp(template)
        text = await extract_text(temp_path)

        if not text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in file.")

        generated_lease = await generate_lease_content(text, fields.model_dump())

        file_id_str = str(uuid4())
        original_name = Path(template.filename).stem
        safe_name = f"{original_name}_generated_lease.docx"
        file_path = dir_path / f"{file_id_str}.docx"
        
        await save_text_as_docx(generated_lease, str(file_path), key="lease_content")

        db_file = await save_file_to_db(
            name=safe_name,
            path=file_path,
            category=category,
            building_id=None,
            user_id=current_user.id,
            db=db
        )
        return db_file

    except ValueError as ve:
        logger.error(f"Error generating lease: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error generating lease: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating lease: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/report-summarizer", response_model=FileResponse)
async def summarize(
    category: str,
    file: UploadFile = FastFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, None, current_user, db)
    await check_subscription(current_user, db)

    content = await validate_pdf_upload(file)

    clean_text = await generate_pdf_summary(content)

    dir_path = UPLOAD_DIR / "outer" / str(category)
    dir_path.mkdir(parents=True, exist_ok=True)

    file_id_str = str(uuid4())
    original_name = Path(file.filename).stem
    safe_name = f"{original_name}_report_summary.docx"
    file_path = dir_path / f"{file_id_str}.docx"
    
    await save_text_as_docx(clean_text, str(file_path), key="report_summary")

    db_file = await save_file_to_db(
        name=safe_name,
        path=file_path,
        category=category,
        building_id=None,
        user_id=current_user.id,
        db=db
    )

    try:
        num_chunks = await process_and_store_universal(
            text=clean_text,
            filename=file.filename,
            user_id=current_user.id,
            category=category,
            file_id=db_file.id,
            building_id=None,
        )
        
        logger.info(f"Saved summary file {db_file.id} with {num_chunks} chunks.")
    except Exception as e:
        try:
            success = await clear_file(db_file.id, db_file.path)
            if not success:
                logger.error(f"Failed to clear vectors and file for file ID {db_file.id}")
        except Exception as e:
            logger.error(f"Error during cleanup after failed upload: {e}")
        
        await db.delete(db_file)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Indexing error: {e}")
   
    return db_file
