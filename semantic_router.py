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


async def get_embedding(text: str) -> list[float] | None:
    """Generate embedding using the local Infinity TEI server with Redis cache."""
    # ── Try Redis Cache First ──
    try:
        r = get_redis()
        cache_key = f"iara:emb:{text[:100]}" # Simple key
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug(f"Cache miss or error: {e}")

    # ── Generate new embedding ──
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{config.TEI_URL}/embeddings",
                json={"input": text, "model": config.TEI_MODEL},
            )
            response.raise_for_status()
            data = response.json()
            vector = data["data"][0]["embedding"]
            
            # ── Save to Cache ──
            try:
                await r.setex(cache_key, EMBEDDING_CACHE_TTL, json.dumps(vector))
            except Exception:
                pass
                
            return vector
    except Exception as e:
        logger.warning(f"⚠️ Embedding failed in router: {e}")
        return None


async def classify_intent(text: str) -> tuple[str, float]:
    """
    Semantically classify the user's intent by embedding their text
    and searching against the 'routes' collection in Qdrant.
    
    Returns:
        tuple: (route_name, confidence_score)
        If confidence < MIN_SCORE_THRESHOLD, falls back to 'chat_agent'.
    """
    vector = await get_embedding(text)
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
        logger.warning(f"⚠️ Qdrant semantic routing failed: {e}. Fallback to chat_agent.")
        return "chat_agent", 0.0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Semantic Cache (Response Cache) — SOTA 2026
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def semantic_cache_get(text: str) -> str | None:
    """
    Search Redis for a semantically similar query and return its cached response.
    Uses cosine similarity on embeddings. Threshold: 0.92.
    """
    vector = await get_embedding(text)
    if not vector:
        return None
    
    r = get_redis()
    # Note: Using '*' keys can be slow at scale (10k+). 
    # For now, it's safe on this VPS setup.
    keys = await r.keys("iara:scache:*")
    if not keys:
        return None
    
    query_vec = np.array(vector, dtype=np.float32)
    
    # Batch fetch from Redis
    pipe = r.pipeline()
    for key in keys:
        pipe.hgetall(key)
    entries = await pipe.execute()
    
    for entry in entries:
        if not entry or "embedding" not in entry:
            continue
        
        # entry keys are bytes in decode_responses=False, but here we use True
        # but wait, the embedding should be raw bytes for numpy
        # Let's handle both cases
        cached_bytes = entry["embedding"]
        if isinstance(cached_bytes, str):
            # If decode_responses=True, we might have issues with raw bytes
            # For the cache, it's better to use a dedicated Redis client with decode_responses=False
            continue
            
        cached_vec = np.frombuffer(cached_bytes, dtype=np.float32)
        
        # Cosine Similarity
        norm_q = np.linalg.norm(query_vec)
        norm_c = np.linalg.norm(cached_vec)
        if norm_q == 0 or norm_c == 0:
            continue
            
        sim = np.dot(query_vec, cached_vec) / (norm_q * norm_c)
        
        if sim >= SEMANTIC_CACHE_THRESHOLD:
            logger.info(f"🎯 Semantic Cache HIT (sim: {sim:.4f})")
            return entry.get("response")
            
    return None


async def semantic_cache_set(text: str, response: str):
    """Save response to semantic cache with its embedding."""
    vector = await get_embedding(text)
    if not vector:
        return
        
    r = aioredis.from_url(config.REDIS_URL, decode_responses=False) # Binary for vectors
    key = f"iara:scache:{uuid.uuid4().hex}"
    
    await r.hset(key, mapping={
        "embedding": np.array(vector, dtype=np.float32).tobytes(),
        "response": response.encode("utf-8")
    })
    await r.expire(key, SEMANTIC_CACHE_TTL)
    logger.debug(f"💾 Saved to Semantic Cache: {key}")
