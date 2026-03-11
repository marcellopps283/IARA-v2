"""
memory.py — 3-Layer Semantic Memory for IARA
    Working Memory:  Redis (conversation context, fast, auto-TTL)
    Episodic Memory: Qdrant (conversation summaries, semantic search via embeddings)
    Core Memory:     Postgres (permanent facts, preferences, rules)
"""

import json
import logging
from datetime import datetime

import aiohttp
import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)

import config

logger = logging.getLogger("memory")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Clients (lazy init)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_redis: aioredis.Redis | None = None
_qdrant: AsyncQdrantClient | None = None

QDRANT_COLLECTION = "episodic_memory"
EMBEDDING_DIM = 1024  # intfloat/multilingual-e5-large dimension
WORKING_MEMORY_TTL = 3600 * 6  # 6 hours
MAX_CONVERSATION_MESSAGES = 20


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis


def get_qdrant() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    return _qdrant


async def init():
    """Initialize memory backends. Call once at startup."""
    # Ensure Qdrant collection exists
    qdrant = get_qdrant()
    try:
        collections = await qdrant.get_collections()
        names = [c.name for c in collections.collections]
        if QDRANT_COLLECTION not in names:
            await qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            logger.info(f"✅ Qdrant collection '{QDRANT_COLLECTION}' created (dim={EMBEDDING_DIM})")
        else:
            logger.info(f"✅ Qdrant collection '{QDRANT_COLLECTION}' exists")
    except Exception as e:
        logger.warning(f"⚠️ Qdrant init failed: {e}")

    # Test Redis
    try:
        r = get_redis()
        await r.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis init failed: {e}")

    logger.info("🧠 Memory stack initialized (Redis + Qdrant)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Embeddings via Infinity TEI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def embed(text: str) -> list[float] | None:
    """Generate embedding using the local Infinity TEI server."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.TEI_URL}/embeddings",
                json={"input": text, "model": config.TEI_MODEL},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["data"][0]["embedding"]
                else:
                    logger.warning(f"⚠️ Infinity TEI returned {resp.status}")
                    return None
    except Exception as e:
        logger.warning(f"⚠️ Embedding failed: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Working Memory (Redis) — Current conversation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _conv_key(chat_id: int) -> str:
    return f"iara:conv:{chat_id}"


async def save_message(chat_id: int, role: str, content: str):
    """Save a message to the conversation history in Redis."""
    r = get_redis()
    key = _conv_key(chat_id)
    msg = json.dumps({"role": role, "content": content, "ts": datetime.now().isoformat()})
    await r.rpush(key, msg)
    await r.ltrim(key, -MAX_CONVERSATION_MESSAGES, -1)  # Keep last N
    await r.expire(key, WORKING_MEMORY_TTL)


async def get_conversation(chat_id: int) -> list[dict]:
    """Get conversation history from Redis."""
    r = get_redis()
    key = _conv_key(chat_id)
    messages = await r.lrange(key, 0, -1)
    result = []
    for m in messages:
        try:
            data = json.loads(m)
            result.append({"role": data["role"], "content": data["content"]})
        except (json.JSONDecodeError, KeyError):
            continue
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Episodic Memory (Qdrant) — Conversation summaries
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def save_episode(summary: str, chat_id: int):
    """Save a conversation summary as a searchable episode in Qdrant."""
    vector = await embed(summary)
    if not vector:
        logger.warning("⚠️ Skipping episode save — embedding failed")
        return

    qdrant = get_qdrant()
    import uuid
    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload={
            "summary": summary,
            "chat_id": chat_id,
            "timestamp": datetime.now().isoformat(),
        },
    )
    await qdrant.upsert(collection_name=QDRANT_COLLECTION, points=[point])
    logger.info(f"📝 Episode saved to Qdrant: {summary[:60]}...")


async def search_episodes(query: str, limit: int = 3) -> list[str]:
    """Search episodic memory for relevant past conversations."""
    vector = await embed(query)
    if not vector:
        return []

    qdrant = get_qdrant()
    try:
        results = await qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vector,
            limit=limit,
        )
        return [r.payload["summary"] for r in results if r.score > 0.3]
    except Exception as e:
        logger.warning(f"⚠️ Qdrant search failed: {e}")
        return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core Memory (Postgres) — Permanent facts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _pg_execute(query: str, *args):
    """Execute a query against Postgres using asyncpg."""
    import asyncpg
    conn = await asyncpg.connect(config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


async def _pg_execute_one(query: str, *args):
    """Execute and return a single value."""
    import asyncpg
    conn = await asyncpg.connect(config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        return await conn.fetchval(query, *args)
    finally:
        await conn.close()


async def init_postgres():
    """Create the core_memory table if it doesn't exist."""
    import asyncpg
    conn = await asyncpg.connect(config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS core_memory (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                content TEXT NOT NULL UNIQUE,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("✅ Postgres core_memory table ready")
    except Exception as e:
        logger.warning(f"⚠️ Postgres init failed: {e}")
    finally:
        await conn.close()


async def save_core_fact(category: str, content: str, confidence: float = 1.0):
    """Save a permanent fact to Postgres core memory."""
    import asyncpg
    conn = await asyncpg.connect(config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await conn.execute("""
            INSERT INTO core_memory (category, content, confidence, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (content) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                updated_at = NOW()
        """, category, content, confidence)
        logger.info(f"💾 Core fact saved: [{category}] {content[:60]}")
    finally:
        await conn.close()


async def get_core_facts(limit: int = 10) -> list[dict]:
    """Retrieve permanent facts from Postgres."""
    rows = await _pg_execute(
        "SELECT category, content, confidence FROM core_memory ORDER BY confidence DESC, updated_at DESC LIMIT $1",
        limit,
    )
    return [{"category": r["category"], "content": r["content"], "confidence": r["confidence"]} for r in rows]
