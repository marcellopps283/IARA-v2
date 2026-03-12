"""
memory.py — 2-Layer Semantic Memory for IARA
    Working Memory:  Redis (conversation context, fast, auto-TTL)
    Cognitive Memory: Managed via memory_manager (Mem0 + LightRAG)
"""

import json
import logging
from datetime import datetime

import redis.asyncio as aioredis
import config
import memory_manager

logger = logging.getLogger("memory")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Clients (lazy init)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_redis: aioredis.Redis | None = None

WORKING_MEMORY_TTL = 3600 * 6  # 6 hours
MAX_CONVERSATION_MESSAGES = 20


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis


async def init():
    """Initialize memory backends. Call once at startup."""
    # Test Redis
    try:
        r = get_redis()
        await r.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis init failed: {e}")

    logger.info("🧠 Memory stack initialized (Redis)")


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
# Episodic Memory — Conversation summaries (Proxy to Mem0)
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
# Core Memory — Permanent facts (Proxy to Mem0)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

