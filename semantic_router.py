"""
semantic_router.py — Vector-based Intent Routing for IARA
Replaces hardcoded keyword lists with semantic search against Qdrant anchors.
"""

import logging
import httpx
from qdrant_client import AsyncQdrantClient

import config

logger = logging.getLogger("semantic_router")

_qdrant: AsyncQdrantClient | None = None
COLLECTION_NAME = "routes"
MIN_SCORE_THRESHOLD = 0.82  # Cosine similarity threshold


def get_qdrant() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    return _qdrant


async def get_embedding(text: str) -> list[float] | None:
    """Generate embedding using the local Infinity TEI server."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{config.TEI_URL}/embeddings",
                json={"input": text, "model": config.TEI_MODEL},
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
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
        results = await qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=1,
            with_payload=True,
        )
        
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
