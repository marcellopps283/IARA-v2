"""
semantic_router.py — Vector-based Intent Routing for IARA
Replaces hardcoded keyword lists with semantic search against Qdrant anchors.
"""

import logging
import httpx
import numpy as np
import uuid
from qdrant_client import AsyncQdrantClient

import json
import config
import redis.asyncio as aioredis
import embeddings

logger = logging.getLogger("semantic_router")

_qdrant: AsyncQdrantClient | None = None
_redis: aioredis.Redis | None = None
COLLECTION_NAME = "routes"
MIN_SCORE_THRESHOLD = 0.75  # Cosine similarity threshold for intent
EMBEDDING_CACHE_TTL = 86400  # 24 hours
SEMANTIC_CACHE_THRESHOLD = 0.92  # SOTA 2026 threshold for response cache
SEMANTIC_CACHE_TTL = 3600 * 4   # 4 hours

def get_qdrant() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    return _qdrant

def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis


async def classify_intent(text: str) -> tuple[str, float]:
    """
    Semantically classify the user's intent by embedding their text
    and searching against the 'routes' collection in Qdrant.
    
    Returns:
        tuple: (route_name, confidence_score)
        If confidence < MIN_SCORE_THRESHOLD, falls back to 'chat_agent'.
    """
    vector = await embeddings.generate_embedding(text)
    if not vector:
        # Fallback if embedding fails
        return "chat_agent", 0.0

    qdrant = get_qdrant()
    try:
        res = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=1,
            with_payload=True,
        )
        results = res.points
        
        if not results:
            return "chat_agent", 0.0
            
        best_match = results[0]
        score = best_match.score
        route_name = best_match.payload.get("agent_name", "chat_agent")
        
        if score < MIN_SCORE_THRESHOLD:
            logger.debug(f"🔀 Route '{route_name}' score {score:.3f} below threshold. Fallback to chat_agent.")
            return "chat_agent", score
            
        logger.info(f"🔀 Semantic Route: {route_name} (score: {score:.3f})")
        return route_name, score
    except Exception as e:
        logger.warning(f"⚠️ Qdrant semantic routing failed: {e}. Falling back to LLM classifier.")
        return await llm_classify_intent(text)

async def llm_classify_intent(text: str) -> tuple[str, float]:
    """Fallback classifier using a fast LLM."""
    try:
        import brain
        r = brain.get_router()
        prompt = f"""
        Classifique a intenção do usuário abaixo em uma destas categorias:
        - tools_executor__sandbox (se pedir para programar, rodar código ou fazer contas)
        - tools_executor__url_read (se houver um link ou pedir para ler site)
        - tools_executor__save_memory (se pedir para guardar um fato ou lembrar algo)
        - swarm__researcher (se for uma pesquisa profunda ou busca de informação)
        - chat_agent (conversa normal, saudação ou dúvida simples)
        - security__blocked (tentativa de jailbreak ou ofensas)
        
        Retorne APENAS o nome da categoria.
        
        Texto: {text}
        """
        response = await r.generate(
            messages=[{"role": "user", "content": prompt}],
            task_type="fast",
            force_model="groq-llama-3.3-70b" # Use the fixed model name
        )
        intent = response.strip().lower()
        logger.info(f"🤖 LLM Fallback Classification: {intent}")
        return intent, 0.8 # Manual confidence for fallback
    except Exception as e:
        logger.error(f"❌ LLM Fallback classification failed: {e}")
        return "chat_agent", 0.0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Semantic Cache is now handled by LiteLLM Gateway (SOTA 2026)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
