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
    """Generate a single embedding using the local Infinity TEI server with Redis cache."""
    results = await generate_embeddings([text])
    return results[0] if results else None

async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate batch embeddings using the local Infinity TEI server with Redis cache."""
    if not texts:
        return []

    r = get_redis()
    results = [None] * len(texts)
    to_fetch_indices = []
    to_fetch_texts = []

    # ── Try Redis Cache First ──
    for i, text in enumerate(texts):
        try:
            cache_key = f"iara:emb:{text[:100]}"
            cached = await r.get(cache_key)
            if cached:
                results[i] = json.loads(cached)
            else:
                to_fetch_indices.append(i)
                to_fetch_texts.append(text)
        except Exception as e:
            logger.debug(f"Embedding cache error for index {i}: {e}")
            to_fetch_indices.append(i)
            to_fetch_texts.append(text)

    if not to_fetch_texts:
        return [r for r in results if r is not None]

    # ── Generate new embeddings ──
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{config.TEI_URL}/embeddings",
                json={"input": to_fetch_texts, "model": config.TEI_MODEL},
            )
            response.raise_for_status()
            data = response.json()
            
            # TEI returns a list of embeddings in "data" field
            for meta_idx, item in enumerate(data["data"]):
                vector = item["embedding"]
                original_idx = to_fetch_indices[meta_idx]
                results[original_idx] = vector
                
                # ── Save to Cache ──
                try:
                    text = to_fetch_texts[meta_idx]
                    cache_key = f"iara:emb:{text[:100]}"
                    await r.setex(cache_key, EMBEDDING_CACHE_TTL, json.dumps(vector))
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"⚠️ Infinity TEI Batch failed: {e}")
        # Return what we have from cache if part of batch failed
        
    return [res for res in results if res is not None]

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
