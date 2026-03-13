"""
config.py — Central Configuration for IARA Ecosystem
Loads environment variables and defines LLM provider routing table.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Database & Infrastructure
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
TEI_URL = os.getenv("TEI_URL", "http://infinity:7997")
TEI_MODEL = os.getenv("TEI_MODEL", "intfloat/multilingual-e5-large")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Telegram
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT2_TOKEN = os.getenv("TELEGRAM_BOT2_TOKEN", "")
TELEGRAM_ALLOWED_CHAT_IDS = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Safety & Guardrails (HITL Policy)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAX_DAILY_LLM_CALLS = int(os.getenv("MAX_DAILY_LLM_CALLS", "2000"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
DB_PATH = os.getenv("DB_PATH", "iara_memory.db")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Identity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SOUL_FILE = os.getenv("SOUL_FILE", "/app/roles/soul.md")

def load_identity() -> str:
    """Load the soul/identity prompt from file, or return a default."""
    try:
        with open(SOUL_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "Você é a IARA — Inteligência Artificial de Raciocínio Autônomo. "
            "Assistente pessoal do Marcello (seu Criador). "
            "Responda de forma direta, inteligente e humanizada, em português brasileiro. "
            "Seja proativa: se o Criador perguntar algo que exige pesquisa, pesquise. "
            "Se precisar de código, escreva. Se não souber, diga."
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM Providers — Multi-Provider Routing Table
# Order matters for fallback priority within each task type.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLM_PROVIDERS = [
    # ── Groq (Primary — Llama 3.3 70B, ultra-fast) ──
    {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 4096,
        "supports_tools": True,
        "supports_streaming": True,
    },
    {
        "name": "groq_2",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY_2", ""),
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 4096,
        "supports_tools": True,
        "supports_streaming": True,
    },
    # ── Cerebras (Fast tasks — Llama 3.1 8B) ──
    {
        "name": "cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": os.getenv("CEREBRAS_API_KEY", ""),
        "model": "llama3.1-8b",
        "max_tokens": 4096,
        "supports_tools": False,
        "supports_streaming": True,
    },
    {
        "name": "cerebras_2",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": os.getenv("CEREBRAS_API_KEY_2", ""),
        "model": "llama3.1-8b",
        "max_tokens": 4096,
        "supports_tools": False,
        "supports_streaming": True,
    },
    # ── OpenRouter (DeepSeek R1 — Heavy reasoning) ──
    {
        "name": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "model": "deepseek/deepseek-r1:free",
        "max_tokens": 8192,
        "supports_tools": False,
        "supports_streaming": True,
    },
    # ── Gemini (Vision + multimodal) ──
    {
        "name": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model": "gemini-2.0-flash",
        "max_tokens": 8192,
        "supports_tools": True,
        "supports_streaming": True,
    },
    # ── Mistral (Code + fallback) ──
    {
        "name": "mistral",
        "base_url": "https://api.mistral.ai/v1",
        "api_key": os.getenv("MISTRAL_API_KEY", ""),
        "model": "mistral-large-latest",
        "max_tokens": 4096,
        "supports_tools": True,
        "supports_streaming": True,
    },
    # ── NVIDIA NIM (Kimi — Long context research) ──
    {
        "name": "kimi",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": os.getenv("NVIDIA_API_KEY", ""),
        "model": "moonshotai/kimi-k2-instruct",
        "max_tokens": 8192,
        "supports_tools": False,
        "supports_streaming": True,
    },
    # ── SambaNova (Extra fallback) ──
    {
        "name": "sambanova",
        "base_url": "https://api.sambanova.ai/v1",
        "api_key": os.getenv("SAMBANOVA_API_KEY", ""),
        "model": "Meta-Llama-3.1-405B-Instruct",
        "max_tokens": 4096,
        "supports_tools": False,
        "supports_streaming": True,
    },
    # ── DashScope International (SOTA 2026) ──
    {
        "name": "dashscope",
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-2.5-coder-32b-instruct",
        "max_tokens": 4096,
        "supports_tools": True,
        "supports_streaming": True
    },
    {
        "name": "dashscope-vl",
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-vl-plus",
        "max_tokens": 4096,
        "supports_tools": False,
        "supports_streaming": True
    },
    # ── MiniMax International ──
    {
        "name": "minimax",
        "api_key": os.getenv("MINIMAX_API_KEY"),
        "base_url": "https://api.minimax.io/v1",
        "model": "minimax-m2.5",
        "max_tokens": 8192,
        "supports_tools": True,
        "supports_streaming": True
    },
]
