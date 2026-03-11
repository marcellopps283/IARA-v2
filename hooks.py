"""
hooks.py — Security Hooks for IARA Ecosystem
Obfuscates API keys and sensitive data before sending prompts to LLMs.
Prevents accidental key leakage through prompt injection or model output.
"""

import os
import re
import logging

logger = logging.getLogger("hooks")

# Patterns that look like API keys/tokens (long alphanumeric strings with dashes)
_KEY_PATTERNS = [
    re.compile(r'(sk-[a-zA-Z0-9]{20,})'),           # OpenAI-style
    re.compile(r'(gsk_[a-zA-Z0-9]{20,})'),           # Groq-style
    re.compile(r'(xai-[a-zA-Z0-9]{20,})'),           # Various AI
    re.compile(r'(nvapi-[a-zA-Z0-9\-]{20,})'),       # NVIDIA NIM
    re.compile(r'([0-9]{8,}:[A-Za-z0-9_\-]{30,})'),  # Telegram bot tokens
]

# Collect actual env values to match against
_sensitive_values = set()

def _load_sensitive_values():
    """Load actual secret values from environment for exact matching."""
    global _sensitive_values
    keys_to_watch = [
        "GROQ_API_KEY", "GROQ_API_KEY_2",
        "CEREBRAS_API_KEY", "CEREBRAS_API_KEY_2",
        "OPENROUTER_API_KEY", "GEMINI_API_KEY",
        "MISTRAL_API_KEY", "NVIDIA_API_KEY",
        "SAMBANOVA_API_KEY", "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BOT2_TOKEN", "DATABASE_URL",
    ]
    for key in keys_to_watch:
        val = os.getenv(key, "")
        if val and len(val) > 8:
            _sensitive_values.add(val)

_load_sensitive_values()


async def before_submit_prompt(text: str) -> str:
    """
    Sanitize text before sending to an LLM.
    Replaces any detected API keys with [REDACTED].
    """
    if not text:
        return text

    sanitized = text

    # Exact match against known env values
    for val in _sensitive_values:
        if val in sanitized:
            sanitized = sanitized.replace(val, "[REDACTED]")
            logger.warning("🛡️ Chave sensível detectada e removida do prompt!")

    # Pattern match for unknown keys
    for pattern in _KEY_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)

    return sanitized
