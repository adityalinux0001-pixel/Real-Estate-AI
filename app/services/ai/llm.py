import asyncio
import io
import json
from fastapi import HTTPException
import google.generativeai as genai
from app.schemas.service import InvoiceMetadata
from app.utils.prompts import (
    GEMINI_CHAT_PROMPT,
    GENERATE_LEASE,
    INVOICE_METADATA,
    GENERAL_PROMPT_TEMPLATE, 
    CLASSIFICATION_PROMPT,
    CLEANING_PROMPT_TEMPLATE,
    LEASE_ABSTRACT,
    GENERATE_SUMMARY_PROMPT,
    SUMMARY_PROMPT_TEMPLATE
)
from typing import List, Dict
from app.core.config import get_settings

settings = get_settings()
genai.configure(api_key=settings.GEMINI_API_KEY)

llm_model = genai.GenerativeModel(settings.GEMINI_MODEL)

json_model = genai.GenerativeModel(
    model_name=settings.GEMINI_MODEL,
    generation_config=genai.GenerationConfig(
        temperature=0.2,
        response_mime_type="application/json"
    ),
)


async def generate_embeddings(chunks: List[str]) -> List[List[float]]:
    loop = asyncio.get_running_loop()

    async def embed_one(text: str) -> List[float]:
        response = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL,
                content=text,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=settings.EMBEDDING_DIMENSION,
            ),
        )

        if isinstance(response, dict) and "embedding" in response:
            return [float(x) for x in response["embedding"]]
        elif hasattr(response, "embedding"):
            return [float(x) for x in response.embedding.values]
        else:
            raise ValueError(f"Unexpected Gemini response: {response}")

    tasks = [embed_one(chunk) for chunk in chunks]
    embeddings = await asyncio.gather(*tasks)
    return embeddings


async def generate_response(classification: str, query: str, contexts: List[str]) -> str:
    
    def _blocking_chat():
        if classification == "summary":
            prompt = SUMMARY_PROMPT_TEMPLATE.format(summary=" ".join(contexts), query=query)
        else:
            prompt = GENERAL_PROMPT_TEMPLATE.format(query=query)
            
        response = llm_model.generate_content(prompt)
        return response.text.strip()

    return await asyncio.to_thread(_blocking_chat)


async def classify_query(query: str) -> str:
    prompt = CLASSIFICATION_PROMPT.format(query=query)
    response = await llm_model.generate_content_async(prompt)
    return response.text.strip().lower()


async def clean_and_structure_text(text: str) -> str:
    prompt = CLEANING_PROMPT_TEMPLATE.format(text=text)
    response = await llm_model.generate_content_async(prompt)
    structured_text = response.text.strip()

    # Remove leftover symbols
    structured_text = structured_text.replace("**", "")
    structured_text = structured_text.replace("*", "")
    structured_text = structured_text.replace("###", "")
    structured_text = structured_text.replace("*******", "")
    structured_text = "\n".join(line for line in structured_text.splitlines() if line.strip())
    return structured_text


async def generate_lease_abstract(lease_text: str) -> str:
    prompt = LEASE_ABSTRACT.format(text=lease_text)

    def _blocking_generate():
        response = llm_model.generate_content(prompt)
        return response.text.strip()

    abstract_text = await asyncio.to_thread(_blocking_generate)
    return abstract_text


async def gemini_chat(query: str) -> str:
    prompt = GEMINI_CHAT_PROMPT.format(query=query)
    def _blocking_chat():
        response = llm_model.generate_content(prompt)
        return response.text.strip()

    return await asyncio.to_thread(_blocking_chat)


async def generate_lease_content(text: str, fields: Dict[str, str]):
    print("fields:", fields)
    prompt = GENERATE_LEASE.format(template=text, fields=fields)
    def _blocking_generate():
        response = llm_model.generate_content(prompt)
        return response.text.strip()

    text = await asyncio.to_thread(_blocking_generate)
    return text


async def extract_invoice_metadata(text: str) -> InvoiceMetadata:
    prompt = INVOICE_METADATA.format(text=text)

    def _blocking_generate():
        response = json_model.generate_content(prompt)
        return response.text

    raw = await asyncio.to_thread(_blocking_generate)

    try:
        metadata_json = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON from Gemini: {raw}")

    return InvoiceMetadata(**metadata_json)


async def generate_pdf_summary(content: bytes) -> str:
    pdf_file = genai.upload_file(io.BytesIO(content), mime_type="application/pdf")
    
    try:
        response = llm_model.generate_content(
            [GENERATE_SUMMARY_PROMPT, pdf_file],
            generation_config={"temperature": 0.1}
        )
        return response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")
    finally:
        try:
            genai.delete_file(pdf_file.name)
        except:
            pass
