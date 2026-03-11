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
import memory_manager

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
    """Save a conversation summary as a searchable episode in Mem0."""
    await memory_manager.add_core_memory(summary, user_id=f"session_{chat_id}")
    logger.info(f"📝 Episode saved to Mem0: {summary[:60]}...")


async def search_episodes(query: str, chat_id: int, limit: int = 3) -> list[str]:
    """Search episodic memory for relevant past conversations in Mem0."""
    results_str = await memory_manager.search_core_memory(query, user_id=f"session_{chat_id}", limit=limit)
    if not results_str:
        return []
    
    return [line.lstrip("- ").strip() for line in results_str.split("\n") if line.strip()]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core Memory (Postgres) — Permanent facts (connection pool)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import asyncpg

_pg_pool: asyncpg.Pool | None = None


def _pg_dsn() -> str:
    return config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def init_postgres():
    """Create connection pool and core_memory table."""
    global _pg_pool
    try:
        _pg_pool = await asyncpg.create_pool(
            _pg_dsn(),
            min_size=2,
            max_size=10,
        )
        async with _pg_pool.acquire() as conn:
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
        logger.info("✅ Postgres core_memory table ready (pool: 2-10 connections)")
    except Exception as e:
        logger.warning(f"⚠️ Postgres init failed: {e}")


async def save_core_fact(category: str, content: str, confidence: float = 1.0):
    """Save a permanent fact to Mem0 core memory."""
    await memory_manager.add_core_memory(f"[{category}] {content}", user_id="creator")
    logger.info(f"💾 Core fact saved via Mem0: [{category}] {content[:60]}")


async def get_core_facts(limit: int = 10) -> list[dict]:
    """Retrieve permanent facts from Mem0."""
    results_str = await memory_manager.search_core_memory("Preferências e fatos importantes", user_id="creator", limit=limit)
    if not results_str:
        return []
    
    facts = []
    for line in results_str.split("\n"):
        if line.strip():
            facts.append({"category": "mem0", "content": line.lstrip("- ").strip(), "confidence": 1.0})
    return facts

