from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File as FastAPIFile, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.database import get_db
from app.core.security import check_subscription
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.file import FileResponse
from app.services.ai.chat import append_message
from app.services.ai.rag import query_with_universal_rag
from app.services.file.service import clear_file, save_file_to_db
from app.services.file_processing import extract_text
from app.services.ai.smart_chunker import process_and_store_universal
from app.services.ai.llm import extract_invoice_metadata
from app.services.service import save_invoice_to_db
from app.utils.helpers import get_or_create_session, validate_category, save_file
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["Additional Services"])
UPLOAD_DIR = Path("uploads")


@router.post("/invoice/upload", response_model=FileResponse)
async def upload_invoice(
    category: str,
    building_id: int,
    file: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_category(category, building_id, current_user, db)
    await check_subscription(current_user, db)

    dir_path = UPLOAD_DIR / str(building_id) / category
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

        metadata = await extract_invoice_metadata(text)

        await save_invoice_to_db(
            file_id=db_file.id,
            building_id=building_id,
            user_id=current_user.id,
            metadata=metadata,
            db=db
        )

        await process_and_store_universal(
            text=text,
            filename=file.filename,
            user_id=current_user.id,
            category=category,
            file_id=db_file.id,
            building_id=building_id,
        )

        return db_file

    except Exception as e:
        try:
            await clear_file(db_file.id, db_file.path)
        except:
            pass

        await db.delete(db_file)
        await db.commit()

        raise HTTPException(status_code=500, detail=f"Failed to process invoice: {str(e)}")


@router.post("/invoices/chat", response_model=ChatResponse)
async def chat_with_invoice_service(request: ChatRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    building_id = request.building_id
    category = request.category
    
    await check_subscription(current_user, db)
    await validate_category(category, building_id, current_user, db)
    
    try:
        await get_or_create_session(request, current_user, db)

        await append_message(db, request.session_id, "user", request.query)
        response = await query_with_universal_rag(request.query, current_user.id, request.file_id, building_id, category)
        await append_message(db, request.session_id, "assistant", response)

        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")

