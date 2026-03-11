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
import memory
import sandbox
import mcp_client
import swarm
import council

logger = logging.getLogger("brain")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CODE_BLOCK_REGEX = re.compile(r'```(?:python)?\n(.+?)```', re.DOTALL)

CODE_KEYWORDS = [
    "executa", "execute", "roda esse código", "roda isso",
    "testa esse código", "run this", "eval",
]

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

MEMORY_SAVE_KEYWORDS = [
    "lembra que", "lembre que", "memoriza", "memorize",
    "guarda isso", "salva isso", "anota isso", "não esquece",
    "grava isso", "registra",
]

MEMORY_RECALL_KEYWORDS = [
    "o que você sabe sobre mim", "o que sabe de mim",
    "o que você lembra", "o que lembra de mim",
    "minhas preferências", "meus dados",
]

URL_REGEX = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def classify_intent(text: str) -> tuple[str, str | None]:
    """Fast keyword-based intent classification."""
    text_lower = text.lower().strip()

    # Code block detected → sandbox execution
    code_match = CODE_BLOCK_REGEX.search(text)
    if code_match:
        return ("execute_code", code_match.group(1).strip())

    for kw in CODE_KEYWORDS:
        if kw in text_lower:
            return ("execute_code", text)

    urls = URL_REGEX.findall(text)
    if urls:
        return ("url_read", urls[0])

    for kw in MEMORY_SAVE_KEYWORDS:
        if kw in text_lower:
            fact = text_lower
            for k in MEMORY_SAVE_KEYWORDS:
                fact = fact.replace(k, "").strip()
            return ("save_memory", fact or text)

    for kw in MEMORY_RECALL_KEYWORDS:
        if kw in text_lower:
            return ("recall_memory", None)

    for kw in REASONING_KEYWORDS:
        if kw in text_lower:
            return ("reasoning", None)

    for kw in SEARCH_KEYWORDS:
        if kw in text_lower:
            query = text_lower
            for k in SEARCH_KEYWORDS:
                query = query.replace(k, "").strip()
            return ("search", query or text)

    return ("chat", None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Brain Core — Main Processing Pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global router
    if router is None:
        router = LLMRouter()
    return router


def build_system_prompt(core_facts: list[dict] | None = None, episodes: list[str] | None = None) -> str:
    """Build system prompt with identity + memory layers + temporal context."""
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

    # Memory layers
    memory_section = ""
    if core_facts:
        facts_text = "\n".join(f"- [{f['category']}] {f['content']}" for f in core_facts)
        memory_section += f"\n\n[MEMÓRIA PERMANENTE — Fatos sobre o Criador]\n{facts_text}"
    if episodes:
        episodes_text = "\n".join(f"- {ep}" for ep in episodes)
        memory_section += f"\n\n[MEMÓRIA EPISÓDICA — Conversas passadas relevantes]\n{episodes_text}"

    return f"""{identity}

{time_str}
{memory_section}

Responda sempre em português brasileiro, de forma direta e inteligente.
Você é a IARA rodando na VPS — autônoma, rápida, com memória semântica."""


async def process(text: str, chat_id: int) -> str:
    """
    Main brain pipeline.
    1. Save user message to working memory
    2. Classify intent
    3. Execute memory actions if needed
    4. Retrieve memory context
    5. Build prompt with conversation + memory
    6. Call LLM
    7. Save assistant response to working memory
    """
    r = get_router()

    # 1. Save user message to Redis
    await memory.save_message(chat_id, "user", text)

    # 2. Classify intent
    intent, extra = classify_intent(text)
    logger.info(f"🎯 Intent: {intent} | Extra: {extra}")

    # 3. Handle memory intents directly
    if intent == "save_memory" and extra:
        await memory.save_core_fact("fato", extra)
        response = f"✅ Memorizado: \"{extra}\""
        await memory.save_message(chat_id, "assistant", response)
        return response

    if intent == "recall_memory":
        facts = await memory.get_core_facts(limit=20)
        if facts:
            facts_text = "\n".join(f"• [{f['category']}] {f['content']}" for f in facts)
            response = f"🧠 **Tudo que sei sobre você:**\n\n{facts_text}"
        else:
            response = "🧠 Ainda não tenho fatos permanentes salvos sobre você."
        await memory.save_message(chat_id, "assistant", response)
        return response

    # 3b. Handle code execution via Docker sandbox
    if intent == "execute_code" and extra:
        logger.info(f"🐳 Executing code in sandbox...")
        output = await sandbox.execute_python(extra)
        response = f"🐳 **Resultado da execução:**\n```\n{output}\n```"
        await memory.save_message(chat_id, "assistant", response)
        return response

    # 3c. Handle URL reading via aiohttp
    if intent == "url_read" and extra:
        logger.info(f"🌐 Fetching URL: {extra}")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(extra, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    content = await resp.text()
            if len(content) > 8000:
                content = content[:8000] + "\n[... truncado]"
            messages = [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": f"O usuário enviou esta URL: {extra}\n\nConteúdo da página:\n{content}\n\nMensagem original: {text}"}
            ]
            r = get_router()
            response = await r.generate(messages=messages, task_type="chat", temperature=0.5)
            response = response or "Não consegui processar o conteúdo."
        except Exception as e:
            logger.warning(f"⚠️ URL fetch failed: {e}")
            response = f"⚠️ Não consegui acessar essa URL: {e}"
        await memory.save_message(chat_id, "assistant", response)
        return response

    # 3d. Council debate (adversarial analysis)
    if council.should_use_council(text):
        logger.info("⚖️ Invoking Council debate...")
        response = await council.debate(text)
        await memory.save_message(chat_id, "assistant", response)
        return response

    # 3e. Specialist dispatch (Swarm)
    specialist = swarm.detect_specialist(text)
    if specialist:
        logger.info(f"🐝 Delegating to specialist: {specialist}")
        conversation = await memory.get_conversation(chat_id)
        context = "\n".join(f"{m['role']}: {m['content']}" for m in conversation[-6:])
        response = await swarm.dispatch(specialist, text, context=context)
        await memory.save_message(chat_id, "assistant", response)
        return response

    # 4. Retrieve memory context
    task_type = "reasoning" if intent == "reasoning" else "chat"
    core_facts = await memory.get_core_facts(limit=5)
    episodes = await memory.search_episodes(text, limit=3)

    # 5. Build messages with conversation history
    system_prompt = build_system_prompt(core_facts=core_facts, episodes=episodes)
    conversation = await memory.get_conversation(chat_id)

    messages = [{"role": "system", "content": system_prompt}]
    # Add conversation history (already includes the current user message)
    messages.extend(conversation)

    # 6. Call LLM
    try:
        response = await r.generate(
            messages=messages,
            task_type=task_type,
            temperature=0.7,
        )

        if isinstance(response, dict):
            response = f"[Tool Call] {response}"

        response = response or "..."

    except RuntimeError as e:
        logger.error(f"❌ All LLM providers failed: {e}")
        response = "⚠️ Desculpa Criador, todos os meus cérebros falharam. Tenta de novo!"
    except Exception as e:
        logger.error(f"❌ Brain error: {e}", exc_info=True)
        response = f"❌ Erro interno: {str(e)[:200]}"

    # 7. Save assistant response
    await memory.save_message(chat_id, "assistant", response)

    return response
