import asyncio
from typing import Optional
from fastapi import HTTPException
from app.core.config import get_settings
from app.services.index_manager import initialize_pinecone_index
from app.services.ai.llm import generate_response, classify_query, generate_embeddings
from app.services.ai.rag_service import query_documents_universal

from app.models.user import User
from app.schemas.chat import ChatRequest
import logging


logger = logging.getLogger(__name__)
settings = get_settings()
index = initialize_pinecone_index()


async def clear_vectors(file_id: int) -> bool:
    try:
        await asyncio.to_thread(index.delete, filter={"file_id": str(file_id)})
        return True
    except Exception as e:
        print(f"Error deleting vectors for file_id {file_id}: {e}")
        return False


async def query_with_universal_rag(
    query: str,
    user_id: int,
    file_id: Optional[int] = None,
    building_id: Optional[int] = None,
    category: Optional[str] = None,
) -> str:
    classification = await classify_query(query)

    if classification == "general":
        return await generate_response(classification, query, [])
    
    return await query_documents_universal(query, user_id, file_id, building_id, category)


async def chat_with_file_service(req: ChatRequest, current_user: User):
    logger.info(f"Summary Chat Question: '{req.query}', file_id={req.file_id}")

    try:
        classification = await classify_query(req.query)

        if classification == "general":
            return await generate_response(classification, req.query, [])

        logger.info(f"Query classified as: {classification}")

        query_emb = (await generate_embeddings([req.query]))[0]

        filter_metadata = {
            "user_id": str(current_user.id),
            "category": req.category,
        }
        
        if req.file_id is not None:
            filter_metadata["file_id"] = str(req.file_id)

        if req.building_id is not None:
            filter_metadata["building_id"] = str(req.building_id)
        
        result = await asyncio.to_thread(
            index.query,
            vector=query_emb,
            top_k=5,
            include_metadata=True,
            filter=filter_metadata
        )

        contexts = [match["metadata"]["chunk"] for match in result["matches"]]
        
        if len(contexts) == 0:
            return "The requested information could not be found in your uploaded documents."
        
        return await generate_response("summary", req.query, contexts)

    except Exception as e:
        logger.error(f"Error during summary chat: {str(e)}", exc_info=True)
        raise HTTPException(500, "Error processing summary chat")
