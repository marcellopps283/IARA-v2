"""
settings_manager.py — Dynamic Configuration Persistence
Uses Redis to store and retrieve runtime settings for the IARA ecosystem.
"""

import json
import logging
import os
import redis.asyncio as aioredis
import config

logger = logging.getLogger("settings")

_redis: aioredis.Redis | None = None
SETTINGS_KEY = "iara:settings"

def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis

async def get_settings() -> dict:
    """Retrieve all dynamic settings from Redis or defaults."""
    r = get_redis()
    try:
        data = await r.get(SETTINGS_KEY)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.error(f"Error reading settings from Redis: {e}")
    
    # Defaults
    return {
        "active_model": config.LLM_PROVIDERS[0]["model"],
        "backup_model": config.LLM_PROVIDERS[1]["model"] if len(config.LLM_PROVIDERS) > 1 else "",
        "temperature": 0.5,
        "reasoning_mode": "planning",  # fast | planning
        "log_level": "INFO",
        "enable_cot": True
    }

async def update_settings(updates: dict) -> dict:
    """Merge updates into current settings and save to Redis."""
    current = await get_settings()
    current.update(updates)
    
    r = get_redis()
    try:
        await r.set(SETTINGS_KEY, json.dumps(current))
        logger.info(f"⚙️ Settings updated: {updates}")
    except Exception as e:
        logger.error(f"Error saving settings to Redis: {e}")
    
    return current

async def get_active_model() -> str:
    """Get the currently active model for generation."""
    settings = await get_settings()
    return str(settings.get("active_model", config.LLM_PROVIDERS[0]["model"]))

async def get_reasoning_mode() -> str:
    """Get the current reasoning mode (fast or planning)."""
    settings = await get_settings()
    return str(settings.get("reasoning_mode", "planning"))
