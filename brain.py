"""
brain.py — IARA Core Brain (Clean VPS Architecture)
Pipeline: receive → classify intent → execute tool → call LLM → respond.

This is a clean rewrite designed for the VPS stack.
The old Termux brain.py is reference only.
"""

import logging
import re
from datetime import datetime

import config
from llm_router import LLMRouter

logger = logging.getLogger("brain")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Intent Detection — Keywords (fast, no LLM call)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEARCH_KEYWORDS = [
    "pesquisa", "pesquisar", "busca", "buscar", "procura", "procurar",
    "search", "google", "qual o preço", "quanto custa",
    "quanto tá", "cotação", "notícia", "noticias", "news",
]

REASONING_KEYWORDS = [
    "aprofunde", "aprofunda", "detalha", "explique detalhadamente",
    "refatora", "pense passo a passo", "complexo", "arquitetura",
    "analise criticamente", "pense como especialista",
]

URL_REGEX = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def classify_intent(text: str) -> tuple[str, str | None]:
    """
    Fast keyword-based intent classification.
    Returns (intent, extra_data).
    """
    text_lower = text.lower().strip()

    # URL detected → will read it
    urls = URL_REGEX.findall(text)
    if urls:
        return ("url_read", urls[0])

    # Deep reasoning
    for kw in REASONING_KEYWORDS:
        if kw in text_lower:
            return ("reasoning", None)

    # Web search
    for kw in SEARCH_KEYWORDS:
        if kw in text_lower:
            query = text_lower
            for k in SEARCH_KEYWORDS:
                query = query.replace(k, "").strip()
            return ("search", query or text)

    # Default: chat
    return ("chat", None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Brain Core — Main Processing Pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Singleton router
router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Lazy-init the LLM router."""
    global router
    if router is None:
        router = LLMRouter()
    return router


def build_system_prompt() -> str:
    """Build the system prompt with identity + temporal context."""
    identity = config.load_identity()

    now = datetime.now()
    days_pt = {
        "Monday": "segunda-feira", "Tuesday": "terça-feira",
        "Wednesday": "quarta-feira", "Thursday": "quinta-feira",
        "Friday": "sexta-feira", "Saturday": "sábado", "Sunday": "domingo",
    }
    time_str = now.strftime("Hoje é %A, %d/%m/%Y. São %H:%M (horário de Brasília).")
    for en, pt in days_pt.items():
        time_str = time_str.replace(en, pt)

    return f"""{identity}

{time_str}

Responda sempre em português brasileiro, de forma direta e inteligente.
Se o usuário pedir algo que exige pesquisa ou ferramentas, diga que você está trabalhando nisso.
Você é a IARA rodando na VPS — autônoma, rápida, sem limites de bateria."""


async def process(text: str, chat_id: int) -> str:
    """
    Main brain pipeline.
    Takes user text, processes it, returns response text.
    """
    r = get_router()

    # 1. Classify intent
    intent, extra = classify_intent(text)
    logger.info(f"🎯 Intent: {intent} | Extra: {extra}")

    # 2. Determine task type for LLM routing
    task_type = "chat"
    if intent == "reasoning":
        task_type = "reasoning"

    # 3. Build system prompt
    system_prompt = build_system_prompt()

    # 4. Build messages
    # TODO Phase 6B: inject memory context (Redis conversation + Qdrant episodes)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    # 5. Call LLM
    try:
        response = await r.generate(
            messages=messages,
            task_type=task_type,
            temperature=0.7,
        )

        if isinstance(response, dict):
            # Tool call response — shouldn't happen without tools, but handle gracefully
            return f"[Tool Call] {response}"

        return response or "..."

    except RuntimeError as e:
        logger.error(f"❌ All LLM providers failed: {e}")
        return (
            "⚠️ Desculpa Criador, todos os meus cérebros falharam agora. "
            "Tenta de novo em alguns segundos!"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected brain error: {e}", exc_info=True)
        return f"❌ Erro interno: {str(e)[:200]}"
