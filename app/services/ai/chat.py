from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import desc
from sqlalchemy.future import select
from typing import List, Dict
from app.models.session import ChatSession
from app.models.message import Message


async def get_chat_history(db: AsyncSession, session_id: str, user_id: int, max_messages: int = 10) -> List[Dict[str, str]]:
    result = await db.execute(select(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id))
    session = result.scalars().first()
    if not session:
        raise ValueError("Session not found or unauthorized")

    result = await db.execute(
        select(Message)
        .filter(Message.session_id == session_id)
        .order_by(desc(Message.timestamp))
        .limit(max_messages)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    
    return [{"role": msg.role, "content": msg.content} for msg in messages]


async def append_message(db: AsyncSession, session_id: str, role: str, content: str):
    message = Message(session_id=session_id, role=role, content=content)
    db.add(message)
    await db.commit()
