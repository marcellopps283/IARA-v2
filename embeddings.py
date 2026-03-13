"""
embeddings.py — Central Vector Utilities for IARA
Handles TEI integration, caching, and distance metrics.
"""

import logging
import httpx
import json
import numpy as np
import redis.asyncio as aioredis
import config

logger = logging.getLogger("embeddings")

_redis: aioredis.Redis | None = None
EMBEDDING_CACHE_TTL = 86400  # 24 hours

def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis

async def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding using the local Infinity TEI server with Redis cache."""
    # ── Try Redis Cache First ──
    try:
        r = get_redis()
        cache_key = f"iara:emb:{text[:100]}"
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug(f"Embedding cache miss/error: {e}")

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
        logger.warning(f"⚠️ Infinity TEI failed: {e}")
        return None

def serialize_embedding(vector: list[float]) -> bytes:
    """Convert vector to binary blob for database storage."""
    return json.dumps(vector).encode("utf-8")

def deserialize_embedding(blob: bytes | str) -> list[float] | None:
    """Convert binary blob back to vector list."""
    try:
        if isinstance(blob, bytes):
            return json.loads(blob.decode("utf-8"))
        return json.loads(blob)
    except Exception as e:
        logger.error(f"Error deserializing embedding: {e}")
        return None

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    try:
        a = np.array(v1)
        b = np.array(v2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    except Exception:
        return 0.0
