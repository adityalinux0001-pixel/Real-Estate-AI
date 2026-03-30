import asyncio
from typing import List, Dict, Optional, Any
from app.services.ai.llm import llm_model, generate_embeddings
from app.services.index_manager import initialize_pinecone_index
from app.utils.helpers import safe_parse_json, strip_code_fence
from app.utils.prompts import RAG_PROMPT_TEMPLATE, QUERY_ANALYSIS_TEMPLATE
import logging

logger = logging.getLogger(__name__)


class QueryUnderstanding:
    def __init__(self, llm_model):
        self.llm_model = llm_model

    async def understand_query(self, query: str) -> Dict[str, Any]:
        prompt = QUERY_ANALYSIS_TEMPLATE.format(query=query)

        def _blocking():
            response = self.llm_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            raw = strip_code_fence(response.text.strip())
            return safe_parse_json(raw, {}) or {}

        return await asyncio.to_thread(_blocking)


class UniversalRetriever:
    def __init__(self, llm_model, embedding_function, pinecone_index):
        self.llm_model = llm_model
        self.embedding_function = embedding_function
        self.index = pinecone_index
        self.query_understander = QueryUnderstanding(llm_model)

    async def retrieve(
        self,
        query: str,
        user_id: int,
        file_id: Optional[int],
        building_id: Optional[int],
        category: Optional[str],
        top_k: int = 10
    ) -> (List[Dict[str, Any]], Dict[str, Any]): # type: ignore

        logger.info("→ Understanding query...")
        understanding = await self.query_understander.understand_query(query)

        broaden_filter = {"$and": [{"user_id": {"$eq": str(user_id)}}]}
        
        if category: 
            broaden_filter["$and"].append({"category": {"$eq": category}})
            
        if file_id: 
            broaden_filter["$and"].append({"file_id": {"$eq": str(file_id)}})
            
        if building_id: 
            broaden_filter["$and"].append({"building_id": {"$eq": str(building_id)}})

        logger.info(f"Broaden filter: {broaden_filter}")

        emb = (await self.embedding_function([query]))[0]
        result = await asyncio.to_thread(
            self.index.query,
            vector=emb,
            top_k=top_k,
            include_metadata=True,
            filter=broaden_filter
        )

        matches = result.get("matches", [])
        logger.info(f"Results: {len(matches)}")

        return matches[:top_k], understanding


class ResponseGenerator:
    def __init__(self, llm_model):
        self.llm_model = llm_model

    async def generate_response(self, query: str, results: List[Dict], understanding: Dict) -> str:
        if not results:
            return "I couldn't find any information about that in your uploaded documents."

        contexts = []
        for idx, match in enumerate(results):
            meta = match.get("metadata", {})
            chunk = meta.get("chunk", "")
            tags = []
            if meta.get("primary_entity_value"): tags.append(f"Entity: {meta['primary_entity_value']}")
            if meta.get("doc_type"): tags.append(f"Type: {meta['doc_type']}")
            if meta.get("chunk_title"): tags.append(f"Section: {meta['chunk_title']}")
            contexts.append(f"[Source {idx+1}: {', '.join(tags)}]\n{chunk}")

        context_text = "\n\n---\n\n".join(contexts)

        prompt = RAG_PROMPT_TEMPLATE.format(
            contexts=context_text,
            query=query,
            query_intent=understanding.get("query_intent"),
            information_needed=understanding.get("information_needed")
        )

        def _blocking():
            return self.llm_model.generate_content(prompt).text.strip()

        return await asyncio.to_thread(_blocking)


async def query_documents_universal(
    query: str,
    user_id: int,
    file_id: Optional[int] = None,
    building_id: Optional[int] = None,
    category: Optional[str] = None,
) -> str:

    pinecone_index = initialize_pinecone_index()
    retriever = UniversalRetriever(llm_model, generate_embeddings, pinecone_index)

    results, understanding = await retriever.retrieve(
        query, user_id, file_id, building_id, category, top_k=8
    )

    generator = ResponseGenerator(llm_model)
    return await generator.generate_response(query, results, understanding)
