from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from app.core.database import get_db
from app.core.security import check_subscription
from app.dependencies import get_current_user
from app.models.user import User
from app.services.ai.chat import append_message
from app.services.ai.llm import gemini_chat
from app.services.ai.rag import chat_with_file_service, query_with_universal_rag
from app.models.session import ChatSession
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.session import ChatSessionResponse
from app.utils.helpers import get_or_create_session, validate_category

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_sessions(
    building_id: Optional[int] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_subscription(current_user, db)
    await validate_category(category, building_id, current_user, db)
    query = select(ChatSession).filter(ChatSession.user_id == current_user.id)

    if building_id is not None:
        query = query.filter(ChatSession.building_id == building_id)
    if category is not None:
        query = query.filter(ChatSession.category == category)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/ask", response_model=ChatResponse)
async def chat_with_docs(request: ChatRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    building_id = request.building_id
    category = request.category
    
    await check_subscription(current_user, db)
    await validate_category(category, building_id, current_user, db)
    
    if request.session_id is None:
        raise HTTPException(status_code=404, detail="Invalid session ID")
    
    try:
        await get_or_create_session(request, current_user, db)

        await append_message(db, request.session_id, "user", request.query)
        response = await query_with_universal_rag(request.query, current_user.id, request.file_id, building_id, category)
        await append_message(db, request.session_id, "assistant", response)

        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")
    

@router.post("/gemini", response_model=ChatResponse)
async def gemini_chatbot(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):  
    await check_subscription(current_user, db)
    await validate_category(request.category, None, current_user, db)
    
    if request.session_id is None:
        raise HTTPException(status_code=404, detail="Invalid session ID")
    
    try:
        await get_or_create_session(request, current_user, db)

        await append_message(db, request.session_id, "user", request.query)
        response = await gemini_chat(request.query)
        await append_message(db, request.session_id, "assistant", response)
        
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")


@router.post("/ask_summary", response_model=ChatResponse)
async def ask_summary_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await check_subscription(current_user, db)
    await validate_category(req.category, None, current_user, db)

    if req.session_id is None:
        raise HTTPException(status_code=404, detail="Invalid session ID")
    
    try:
        await get_or_create_session(req, current_user, db)

        await append_message(db, req.session_id, "user", req.query)
        response = await chat_with_file_service(req, current_user)
        await append_message(db, req.session_id, "assistant", response)
        
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")
