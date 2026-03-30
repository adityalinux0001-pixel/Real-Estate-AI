import asyncio
import json
import re
from dataclasses import asdict, dataclass
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
import logging

from app.services.ai.llm import llm_model, generate_embeddings
from app.services.index_manager import initialize_pinecone_index
from app.utils.helpers import safe_parse_json, strip_code_fence

LLM_CONCURRENCY = 10
EMBED_BATCH_SIZE = 100

llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

logger = logging.getLogger(__name__)


async def safe_llm_call(coro):
    """Wraps any LLM call with concurrency control."""
    async with llm_semaphore:
        return await coro


@dataclass
class ChunkMetadata:
    user_id: str
    category: str
    file_id: str
    building_id: Optional[str]

    doc_type: str
    primary_entity_type: Optional[str]
    primary_entity_value: Optional[str]

    section_hierarchy: List[str]
    chunk_title: Optional[str]

    entities: Dict[str, List[str]]
    chunk_type: str
    key_topics: List[str]

    searchable_fields: Dict[str, str]

    chunk_index: int
    total_chunks: int


class DocumentStructureAnalyzer:
    def __init__(self, llm_model):
        self.llm_model = llm_model
    
    async def analyze_structure(self, text: str, filename: str) -> Dict[str, Any]:
        """Comprehensive document analysis"""
        
        prompt = f"""Analyze this document's structure and content. Return JSON ONLY.

        Filename: {filename}
        Content Preview (first 2000 characters):
        {text[:2000]}

        Full document length: {len(text)} characters

        Analyze and return:
        {{
            "doc_type": "lease_agreement|tenant_database|building_specifications|market_report|contact_list|mixed",
            "structure_pattern": "hierarchical_sections|repeated_entries|narrative|tabular|key_value_pairs",
            "primary_entity_type": "tenant|building|lease|broker|property|multiple",
            "entity_count": <number>,
            "is_single_entity": true/false,
            "split_indicators": {{
                "section_markers": ["Article", "Section", "##", "***"],
                "entity_separators": ["Tenant Information Entry", "Building Address:", "---"],
                "hierarchy_patterns": ["numbered lists", "bullet points", "indentation"]
            }},
            "entity_types_present": ["tenant", "building", "broker", "date", "address", "financial"],
            "recommended_chunk_strategy": "by_entity|by_section|by_semantic_block|hybrid",
            "key_field_names": ["Tenant Name", "Building", "Address", "Rent", "Lease Date"]
        }}

        Return ONLY valid JSON, no markdown, no explanation."""       
        
        def _blocking_call():
            response = self.llm_model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json"
                }
            )
            
            raw = response.text.strip()
            raw = strip_code_fence(raw)
            parsed = safe_parse_json(raw, {
                    "doc_type": "mixed",
                    "structure_pattern": "hierarchical_sections",
                    "primary_entity_type": "multiple",
                    "entity_count": 0,
                    "is_single_entity": False,
                    "split_indicators": {
                        "section_markers": ["Article", "Section", "##", "***"],
                        "entity_separators": ["Tenant Information Entry", "Building Address:", "---"],
                        "hierarchy_patterns": ["numbered lists", "bullet points", "indentation"]
                    },
                    "entity_types_present": ["tenant", "building", "broker", "date", "address", "financial"],
                    "recommended_chunk_strategy": "hybrid",
                    "key_field_names": ["Tenant Name", "Building", "Address", "Rent", "Lease Date"]
                }
            )
            return parsed or {}
        return await asyncio.to_thread(_blocking_call)


class DynamicEntityExtractor:
    def __init__(self, llm_model):
        self.llm_model = llm_model  
    
    async def extract_all_entities(
        self,
        text: str,
        entity_types: List[str],
        key_fields: List[str]
    ) -> Dict[str, Any]:

        prompt = f"""Extract ALL entities and key information from this text.

        Text:
        {text[:1500]}

        Expected entity types: {', '.join(entity_types)}
        Key fields to look for: {', '.join(key_fields)}

        Return JSON:
        {{
            "entities": {{
                "tenant": ["name1", "name2"],
                "building": ["address1"],
                "broker": ["broker name"],
                "date": ["2024-01-01"],
                "financial": ["$500,000", "42.00/sf"]
            }},
            "primary_entity": {{
                "type": "tenant|building|lease",
                "value": "main entity name/address"
            }},
            "key_value_pairs": {{
                "Tenant Name": "value",
                "Square Footage": "value",
                "Rent": "value",
                "Lease Expiration": "value"
            }},
            "topics": ["rent terms", "contact information", "building specs"]
        }}

        If information is missing, return empty lists or None. 
        DO NOT include any explanation or text outside the JSON.
        """

        def _blocking_call():
            response = self.llm_model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json"
                }
            )
            raw = response.text.strip()
            raw = strip_code_fence(raw)
            parsed = safe_parse_json(raw, {
                "entities": {},
                "primary_entity": {"type": None, "value": None},
                "key_value_pairs": {},
                "topics": []
            })
            return parsed or {}

        return await asyncio.to_thread(_blocking_call)


class DynamicChunkSplitter:
    @staticmethod
    def split_by_discovered_patterns(
        text: str,
        split_indicators: Dict[str, List[str]],
        structure_pattern: str
    ) -> List[Tuple[str, List[str]]]:
        if structure_pattern == "repeated_entries":
            return DynamicChunkSplitter._split_repeated_entries(text, split_indicators)
        elif structure_pattern == "hierarchical_sections":
            return DynamicChunkSplitter._split_hierarchical(text, split_indicators)
        elif structure_pattern == "tabular":
            return DynamicChunkSplitter._split_tabular(text, split_indicators)
        else:
            return DynamicChunkSplitter._split_semantic_blocks(text)
    
    @staticmethod
    def _split_repeated_entries(
        text: str, 
        split_indicators: Dict[str, List[str]]
    ) -> List[Tuple[str, List[str]]]:
        separators = split_indicators.get('entity_separators', [])
        chunks = []
        
        for separator in separators:
            if not separator:
                continue
            
            escaped_sep = re.escape(separator)
            
            pattern = f'(?:^|\n)({escaped_sep}.*?)(?=(?:\n{escaped_sep}|$))'
            
            matches = list(re.finditer(pattern, text, re.DOTALL))
            
            if len(matches) > 1:  # Found multiple entries
                for idx, match in enumerate(matches):
                    chunk_text = match.group(1).strip()
                    if len(chunk_text) > 50:  # Minimum chunk size
                        hierarchy = [f"{separator} #{idx + 1}"]
                        chunks.append((chunk_text, hierarchy))
                
                if chunks:
                    return chunks
        
        fallback_patterns = [
            r'\n\*\*\*+\n',
            r'\n---+\n',
            r'\n\s*\n\s*\n'
        ]
        
        for pattern in fallback_patterns:
            parts = re.split(pattern, text)
            if len(parts) > 1:
                for idx, part in enumerate(parts):
                    if part.strip() and len(part.strip()) > 50:
                        chunks.append((part.strip(), [f"Entry #{idx + 1}"]))
                if chunks:
                    return chunks
        
        return [(text.strip(), ["Complete Document"])]
    
    @staticmethod
    def _split_hierarchical(
        text: str,
        split_indicators: Dict[str, List[str]]
    ) -> List[Tuple[str, List[str]]]:
        section_markers = split_indicators.get('section_markers', [])
        chunks = []
        
        marker_patterns = []
        for marker in section_markers:
            if marker in ['##', '###']:
                marker_patterns.append(f'^{re.escape(marker)}\\s+(.+?)$')
            elif marker.lower() in ['article', 'section']:
                marker_patterns.append(f'^{marker}\\s+\\d+[:.\\s]+(.+?)$')
            else:
                marker_patterns.append(f'^{re.escape(marker)}\\s*(.+?)$')
        
        if not marker_patterns:
            # Default patterns
            marker_patterns = [
                r'^(Article|ARTICLE)\s+(\d+)[:\.]?\s*(.+?)$',
                r'^(Section|SECTION)\s+(\d+)[:\.]?\s*(.+?)$',
                r'^(##\s+.+?)$',
                r'^(\d+\.)\s+(.+?)$'
            ]
        
        combined_pattern = '|'.join(f'({p})' for p in marker_patterns)
        
        section_starts = []
        for match in re.finditer(combined_pattern, text, re.MULTILINE):
            section_starts.append({
                'pos': match.start(),
                'title': match.group(0).strip(),
                'full_match': match.group(0)
            })
        
        if len(section_starts) > 1:
            for i in range(len(section_starts)):
                start_pos = section_starts[i]['pos']
                end_pos = section_starts[i + 1]['pos'] if i + 1 < len(section_starts) else len(text)
                
                section_text = text[start_pos:end_pos].strip()
                section_title = section_starts[i]['title']
                
                if len(section_text) > 50:
                    chunks.append((section_text, [section_title]))
            
            return chunks
        
        return DynamicChunkSplitter._split_semantic_blocks(text)
    
    @staticmethod
    def _split_tabular(
        text: str,
        split_indicators: Dict[str, List[str]]
    ) -> List[Tuple[str, List[str]]]:
        
        rows = []
        
        key_patterns = [
            r'(?:Building Address|Tenant Name|Address):\s*([^\n]+)',
            r'^([A-Z][^\n]{10,60})$',
        ]
        
        for pattern in key_patterns:
            matches = list(re.finditer(pattern, text, re.MULTILINE))
            if len(matches) > 2:
                for idx in range(len(matches)):
                    start = matches[idx].start()
                    end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                    row_text = text[start:end].strip()
                    
                    if len(row_text) > 30:
                        entity_name = matches[idx].group(1).strip()
                        rows.append((row_text, [f"Entry: {entity_name}"]))
                
                if rows:
                    return rows
        
        return DynamicChunkSplitter._split_semantic_blocks(text)
    
    @staticmethod
    def _split_semantic_blocks(text: str, max_size: int = 2000) -> List[Tuple[str, List[str]]]:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks = []
        current = []
        size = 0
        index = 1

        for para in paragraphs:
            para_len = len(para)

            if size + para_len > max_size and current:
                chunk_text = "\n\n".join(current)
                title = current[0].split("\n")[0][:100]
                chunks.append((chunk_text, [title or f"Semantic Block #{index}"]))
                index += 1
                current = [para]
                size = para_len
            else:
                current.append(para)
                size += para_len

        if current:
            chunk_text = "\n\n".join(current)
            title = current[0].split("\n")[0][:100]
            chunks.append((chunk_text, [title or f"Semantic Block #{index}"]))

        return chunks if chunks else [(text, ["Complete Document"])]


class UniversalChunker:

    def __init__(self, llm):
        self.llm = llm
        self.structure_analyzer = DocumentStructureAnalyzer(llm)
        self.entity_extractor = DynamicEntityExtractor(llm)

    async def chunk_document(self, text, filename, user_id, category, file_id, building_id=None):
        
        logger.info("→ Analyzing document structure...")
        structure = await self.structure_analyzer.analyze_structure(text, filename)

        logger.info(f"  ✓ Doc Type: {structure['doc_type']}")
        logger.info(f"  ✓ Structure: {structure['structure_pattern']}")
        logger.info(f"  ✓ Single Entity: {structure.get('is_single_entity', False)}")

        if structure.get("is_single_entity") and len(text) <= 2000:
            logger.info("→ Single entity document detected - treating as one chunk")
            chunks = [(text, ["Complete Document"])]
        else:
            logger.info("→ Splitting into chunks using discovered patterns...")
            chunks = DynamicChunkSplitter.split_by_discovered_patterns(
                text,
                structure["split_indicators"],
                structure["structure_pattern"]
            )
            logger.info(f"  ✓ Created {len(chunks)} chunks")

        total_chunks = len(chunks)
        
        entity_tasks = [
            safe_llm_call(
                self.entity_extractor.extract_all_entities(
                    chunk_text,
                    structure.get("entity_types_present", []),
                    structure.get("key_field_names", [])
                )
            )
            for chunk_text, _ in chunks
        ]

        entity_results = await asyncio.gather(*entity_tasks)

        enriched = []
        for idx, ((chunk_text, hierarchy), entity_data) in enumerate(
            zip(chunks, entity_results)
        ):
            searchable_fields = {}
            for k, v in (entity_data.get("key_value_pairs") or {}).items():
                searchable_fields[k.lower().replace(" ", "_")] = str(v)

            primary = entity_data.get("primary_entity") or {}

            metadata = ChunkMetadata(
                user_id=str(user_id),
                category=category,
                file_id=str(file_id),
                building_id=str(building_id) if building_id else None,
                doc_type=structure["doc_type"],
                primary_entity_type=primary.get("type"),
                primary_entity_value=primary.get("value"),
                section_hierarchy=hierarchy,
                chunk_title=hierarchy[-1],
                entities=entity_data.get("entities", {}),
                chunk_type=self._determine_chunk_type(entity_data, structure),
                key_topics=entity_data.get("topics", []),
                searchable_fields=searchable_fields,
                chunk_index=idx,
                total_chunks=total_chunks
            )

            enriched.append({
                "text": chunk_text,
                "metadata": asdict(metadata)
            })

        logger.info(f"✓ Successfully processed {len(enriched)} chunks\n")
        return enriched

    def _determine_chunk_type(
        self,
        entity_data: Dict,
        structure: Dict
    ) -> str:
        """Dynamically determine chunk type"""
        
        entity_data = entity_data or {}
        structure = structure or {}

        primary = entity_data.get('primary_entity') or {}
        entity_type = primary.get('type', '')

        # Determine type
        if entity_type == 'tenant':
            return 'tenant_record'
        elif entity_type == 'building':
            return 'building_record'
        elif entity_type == 'lease':
            return 'lease_clause'
        elif structure.get('structure_pattern') == 'hierarchical_sections':
            return 'document_section'
        else:
            return 'information_block'


async def process_and_store_universal(
    text: str,
    filename: str,
    user_id: int,
    category: str,
    file_id: str,
    building_id: Optional[int],
):
    
    pinecone_index = initialize_pinecone_index()
    chunker = UniversalChunker(llm_model)
    chunks = await chunker.chunk_document(
        text, filename, user_id, category, file_id, building_id
    )
    
    chunk_texts = [c['text'] for c in chunks]
    embeddings = await generate_embeddings(chunk_texts)
    
    vectors = []    
    for chunk_data, emb in zip(chunks, embeddings):
        metadata = chunk_data['metadata']

        metadata = {k: v for k, v in metadata.items() if v is not None}

        entities = metadata.get('entities', {})
        if isinstance(entities, dict):
            for entity_type, entity_values in entities.items():
                if isinstance(entity_values, list):
                    metadata[f'entity_{entity_type}'] = [str(v) for v in entity_values[:5]]

            metadata["entities"] = json.dumps(entities)

        searchable_fields = metadata.get('searchable_fields', {})
        for key, value in searchable_fields.items():
            metadata[f'field_{key}'] = str(value)

        metadata.pop('searchable_fields', None)
        
        print("Metadata: ", metadata)

        vectors.append({
            "id": str(uuid4()),
            "values": emb,
            "metadata": {
                **metadata,
                "chunk": chunk_data['text'][:1000]
            }
        })

    for i in range(0, len(vectors), EMBED_BATCH_SIZE):
        batch = vectors[i:i + EMBED_BATCH_SIZE]
        await asyncio.to_thread(pinecone_index.upsert, vectors=batch)

    logger.info(f"✓ Stored {len(vectors)} vectors in Pinecone")
    return len(vectors)
