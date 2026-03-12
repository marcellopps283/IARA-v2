"""
memory_manager.py — Cognitive Memory Abstraction Layer
Integrates Mem0 (for contradiction resolution and core facts) 
and LightRAG (for background knowledge graphs).
"""

import os
import logging
from mem0 import Memory
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
import functools
import numpy as np

import config

logger = logging.getLogger("memory_manager")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Mem0 Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_mem0_instance = None

def get_mem0() -> Memory:
    """Lazy initialization of Mem0 instance."""
    global _mem0_instance
    if _mem0_instance is None:
        groq_cfg = config.LLM_PROVIDERS[0]
        
        # Set environment variables for LiteLLM
        os.environ["GROQ_API_KEY"] = groq_cfg["api_key"]
        os.environ["OPENAI_API_KEY"] = "infinity-api-key"
        os.environ["OPENAI_BASE_URL"] = config.TEI_URL
        
        mem0_config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": config.QDRANT_HOST,
                    "port": config.QDRANT_PORT,
                    "collection_name": "mem0_core"
                }
            },
            "llm": {
                "provider": "litellm",
                "config": {
                    "model": f"groq/{groq_cfg['model']}"
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": config.TEI_MODEL,
                    "openai_base_url": config.TEI_URL,
                    "api_key": "infinity-api-key",
                    "embedding_dims": 1024
                }
            }
        }
        
        _mem0_instance = Memory.from_config(mem0_config)
        logger.info("🧠 Mem0 initialized (LiteLLM + TEI 1024)")
    return _mem0_instance


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LightRAG Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_lightrag_instance = None

async def tei_embedding_func(texts: list[str]) -> np.ndarray:
    """Custom embedding function using Infinity TEI."""
    import httpx
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{config.TEI_URL}/embeddings",
            json={"input": texts, "model": config.TEI_MODEL}
        )
        response.raise_for_status()
        data = response.json()
        return np.array([item["embedding"] for item in data["data"]])

async def custom_llm_func(prompt: str, system_prompt: str | None = None, **kwargs) -> str:
    """Custom LLM function pointing to IARA's own Multi-Provider Router."""
    import llm_router
    router = llm_router.LLMRouter()
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    response = await router.generate(
        messages=messages, 
        task_type="reasoning", 
        temperature=kwargs.get("temperature", 0.5)
    )
    return response if isinstance(response, str) else str(response)

def get_lightrag() -> LightRAG:
    """Lazy initialization of LightRAG instance."""
    global _lightrag_instance
    if _lightrag_instance is None:
        working_dir = "./lightrag_data"
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)
            
        _lightrag_instance = LightRAG(
            working_dir=working_dir,
            llm_model_func=custom_llm_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=1024,
                max_token_size=8192,
                func=tei_embedding_func
            )
        )
        logger.info("🕸️ LightRAG initialized (Graph Knowledge)")
    return _lightrag_instance


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_core_memory(text: str, user_id: str = "creator", agent_id: str | None = None):
    """Adds a fact to Mem0, resolving contradictions automatically."""
    mem0 = get_mem0()
    # Mem0 handles the synchronous add under the hood? It exposes .add()
    # We run it in a thread if it's strictly synchronous
    import asyncio
    metadata = {}
    if agent_id:
        metadata["agent"] = agent_id
        
    def _add():
        return mem0.add(text, user_id=user_id, metadata=metadata)
        
    return await asyncio.to_thread(_add)


async def search_core_memory(query: str, user_id: str = "creator", limit: int = 5) -> str:
    """Searches Mem0 for relevant facts regarding the user."""
    mem0 = get_mem0()
    import asyncio
    
    def _search():
        results = mem0.search(query=query, user_id=user_id, limit=limit)
        if not results:
            return ""
        
        formatted_results = []
        for r in results:
            if isinstance(r, dict):
                formatted_results.append(f"- {r.get('memory', str(r))}")
            else:
                formatted_results.append(f"- {str(r)}")
        return "\n".join(formatted_results)
        
    return await asyncio.to_thread(_search)


async def ingest_knowledge_graph(text: str):
    """Ingests deep research or large texts into LightRAG Knowledge Graph."""
    rag = get_lightrag()
    import asyncio
    # Must initialize storages internally prior to data persistence in LightRAG 1.0+
    await rag.initialize_storages()
    
    # LightRAG .insert() might be async if llm_model_func is async.
    # We will await it.
    await rag.ainsert(text)


async def search_knowledge_graph(query: str, mode: str = "hybrid") -> str:
    """
    Searches LightRAG graph.
    mode can be 'local' (vector), 'global' (graph), or 'hybrid' (both).
    """
    rag = get_lightrag()
    await rag.initialize_storages()
    # aquery is async
    response = await rag.aquery(query, param=QueryParam(mode=mode))
    return response

