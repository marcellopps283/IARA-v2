"""
ops_bot.py — Operational Telegram Bot for IARA
Second Telegram bot (Control Room) for logs, alerts, and system status.
Invisible to the user — only sends to the ops group/chat.
"""

import logging
import os
from datetime import datetime

import aiohttp

logger = logging.getLogger("ops_bot")

OPS_BOT_TOKEN = os.getenv("TELEGRAM_BOT2_TOKEN", "")
OPS_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")  # Same owner for now

_session: aiohttp.ClientSession | None = None


def is_configured() -> bool:
    """Check if the ops bot has a valid token."""
    return bool(OPS_BOT_TOKEN and len(OPS_BOT_TOKEN) > 10)


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def send(text: str, parse_mode: str = "Markdown"):
    """Send a message to the ops channel."""
    if not is_configured():
        logger.debug("Ops bot not configured, skipping notification")
        return

    session = await _get_session()
    url = f"https://api.telegram.org/bot{OPS_BOT_TOKEN}/sendMessage"

    # Truncate if too long
    if len(text) > 4000:
        text = text[:4000] + "\n[... truncado]"

    try:
        async with session.post(url, json={
            "chat_id": OPS_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": True,
        }) as resp:
            if resp.status != 200:
                data = await resp.json()
                logger.warning(f"⚠️ Ops bot failed: {data}")
    except Exception as e:
        logger.warning(f"⚠️ Ops bot error: {e}")


async def log_event(event_type: str, details: str):
    """Log an operational event to the ops channel."""
    icons = {
        "startup": "🟢",
        "shutdown": "🔴",
        "error": "❌",
        "warning": "⚠️",
        "task": "📋",
        "council": "⚖️",
        "swarm": "🐝",
        "memory": "🧠",
        "sandbox": "🐳",
        "llm": "⚡",
    }
    icon = icons.get(event_type, "📌")
    timestamp = datetime.now().strftime("%H:%M:%S")
    await send(f"{icon} `[{timestamp}]` *{event_type.upper()}*\n{details}")


async def log_error(error: Exception, context: str = ""):
    """Log an error to the ops channel."""
    await log_event("error", f"{context}\n```\n{str(error)[:500]}\n```")


async def log_startup():
    """Send startup notification."""
    await log_event("startup", "IARA Core inicializada com sucesso na VPS!")


async def close():
    """Close the HTTP session."""
    if _session and not _session.closed:
        await _session.close()
