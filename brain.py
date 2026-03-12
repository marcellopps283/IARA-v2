"""
brain.py — IARA Core Brain (LangGraph StateGraph Architecture)
Pipeline: receive → semantic route → execute node → format → respond.

Rewritten from if/elif to LangGraph StateGraph for robust state management
and deterministic routing via Semantic Router (Qdrant embeddings).

The public interface remains: process(text, chat_id) -> str
"""

import logging
import re
import asyncio
from datetime import datetime
from typing import TypedDict

from langgraph.graph import StateGraph, END

import config
from llm_router import LLMRouter
import memory
import sandbox
import mcp_client
import swarm
import council
import semantic_router
import settings_manager

logger = logging.getLogger("brain")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# State Definition
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class IaraState(TypedDict, total=False):
    """State that flows through the LangGraph pipeline."""
    text: str                    # User input
    chat_id: int                 # Telegram chat ID
    intent: str                  # Resolved route name from semantic router
    score: float                 # Semantic similarity score
    response: str                # Final response to user
    core_facts: list[dict]       # From Postgres (permanent memory)
    episodes: list[str]          # From Qdrant (episodic memory)
    conversation: list[dict]     # From Redis (working memory)
    task_type: str               # For LLM router prioritization


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Utilities
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Global LLM Router (lazy init)
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def _extract_url(text: str) -> str | None:
    """Extract first URL from text if present."""
    match = re.search(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    return match.group(0) if match else None


def _extract_code(text: str) -> str | None:
    """Extract code from generic markdown blocks."""
    match = re.search(r'```(?:python)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LangGraph Nodes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def router_node(state: IaraState) -> dict:
    """Classify intent via Semantic Router (Qdrant embeddings)."""
    text = state["text"]

    # Save user message to Redis working memory
    await memory.save_message(state["chat_id"], "user", text)

    # Semantic classification
    intent, score = await semantic_router.classify_intent(text)
    logger.info(f"🎯 Semantic Intent: {intent} (score: {score:.3f})")

    # Determine task_type for LLM router prioritization
    task_type = "chat"
    if "research" in intent or "search" in intent:
        task_type = "reasoning"
    elif "code" in intent or "sandbox" in intent:
        task_type = "code"

    return {"intent": intent, "score": score, "task_type": task_type}


async def memory_node(state: IaraState) -> dict:
    """Load memory layers for chat context (core facts + episodes + conversation)."""
    text = state["text"]
    chat_id = state["chat_id"]

    # Load core facts, episodes, and conversation history in parallel
    core_facts, episodes, conversation = await asyncio.gather(
        memory.get_core_facts(limit=5),
        memory.search_episodes(text, chat_id=chat_id, limit=3),
        memory.get_conversation(chat_id)
    )

    return {
        "core_facts": core_facts or [],
        "episodes": episodes or [],
        "conversation": conversation or [],
    }


async def tools_node(state: IaraState) -> dict:
    """Handle tool-based intents: sandbox, URL, memory save/recall, security."""
    intent = state["intent"]
    text = state["text"]
    response = None

    # ── Sandbox (code execution via REDCODER) ──
    if intent == "tools_executor__sandbox":
        code_snippet = _extract_code(text)
        logger.info("🐳 Invoking REDCODER loop...")
        
        # O REDCODER agora cuida da geração (Blue Team) e correção (Red Team)
        result = await sandbox.redcoder_loop(goal=text, initial_code=code_snippet or "")
        
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        iters = result.get("iterations", 1)
        
        if result.get("exit_code") == 0:
            response = (
                f"✅ **REDCODER (gVisor 2026)**\n\n"
                f"**Output:**\n```\n{stdout}\n```\n\n"
                f"*Resolvido em {iters} iteração(ões) com isolamento total.*"
            )
        else:
            response = (
                f"❌ **Falha de Execução (REDCODER):**\n"
                f"```\n{stderr}\n```\n\n"
                f"*O sistema tentou {iters} correções sem sucesso.*"
            )

    # ── URL reading ──
    elif intent == "tools_executor__url_read":
        url = _extract_url(text)
        if not url:
            response = "⚠️ Você esqueceu de incluir a URL na mensagem."
        else:
            logger.info(f"🌐 Fetching URL: {url}")
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        content = await resp.text()
                if len(content) > 8000:
                    content = content[:8000] + "\n[... truncado]"
                r = get_router()
                messages = [
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": f"O usuário enviou esta URL: {url}\n\nConteúdo da página:\n{content}\n\nMensagem original: {text}"}
                ]
                response = await r.generate(messages=messages, task_type="chat", temperature=0.5)
                response = response or "Não consegui processar o conteúdo."
                
                # Injetar o texto longo no Grafo de Conhecimento em background
                import asyncio
                import memory_manager
                asyncio.create_task(memory_manager.ingest_knowledge_graph(content))

            except Exception as e:
                logger.warning(f"⚠️ URL fetch failed: {e}")
                response = f"⚠️ Não consegui acessar essa URL: {e}"

    # ── Memory save ──
    elif intent == "tools_executor__save_memory":
        await memory.save_core_fact("fato_semantico", text)
        response = "✅ Memorizado contextualmente."

    # ── Memory recall ──
    elif intent == "tools_executor__recall_memory":
        facts = await memory.get_core_facts(limit=20)
        if facts:
            facts_text = "\n".join(f"• [{f['category']}] {f['content']}" for f in facts)
            response = f"🧠 **Tudo que sei sobre você:**\n\n{facts_text}"
        else:
            response = "🧠 Ainda não tenho fatos permanentes salvos."

    # ── Security blocked ──
    elif intent == "security__blocked":
        response = "🛡️ **Acesso Negado**: Tentativa de injeção de prompt ou violação de regras detectada."

    # ── Fallback for other tools_executor intents ──
    elif response is None:
        response = f"⚙️ Ferramenta '{intent}' ainda não implementada."

    return {"response": response}


async def council_node(state: IaraState) -> dict:
    """Run Council adversarial debate (Blue Team vs Red Team → Synthesis)."""
    text = state["text"]
    logger.info("⚖️ Invoking Council debate...")
    response = await council.debate(text)
    return {"response": response}


async def swarm_node(state: IaraState) -> dict:
    """Dispatch to a Swarm specialist (Coder, Researcher, Planner, Creative)."""
    intent = state["intent"]
    text = state["text"]
    chat_id = state["chat_id"]

    if intent == "tools_executor__deep_research":
        specialist = "researcher"
    else:
        specialist = intent.replace("swarm__", "")
    logger.info(f"🐝 Delegating to specialist: {specialist}")

    conversation = await memory.get_conversation(chat_id)
    # Cast to list for slicing to satisfy type checker
    history_slice = list(conversation)[-6:]
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history_slice)
    response = await swarm.dispatch(specialist, text, context=context)

    # Alimentar o Grafo de Conhecimento se for pesquisa profunda
    if specialist == "researcher" and response:
        import asyncio
        import memory_manager
        asyncio.create_task(memory_manager.ingest_knowledge_graph(response))

    return {"response": response}


async def chat_node(state: IaraState) -> dict:
    """Standard chat / conversational reasoning via LLM."""
    text = state["text"]
    task_type = state.get("task_type", "chat")

    system_prompt = build_system_prompt(
        core_facts=state.get("core_facts"),
        episodes=state.get("episodes"),
    )

    messages = [{"role": "system", "content": system_prompt}]
    # Add conversation history (already includes the current user message)
    conversation = state.get("conversation", [])
    messages.extend(conversation)

    active_model = await settings_manager.get_active_model()
    
    r = get_router()
    try:
        response = await r.generate(
            messages=messages,
            task_type=task_type,
            temperature=0.7,
            force_model=active_model # Pass the dynamic model
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

    return {"response": response}


async def formatter_node(state: IaraState) -> dict:
    """Save response to working memory + episodic memory (Qdrant)."""
    text = state["text"]
    chat_id = state["chat_id"]
    response = state.get("response", "...")

    # Save assistant response to Redis
    await memory.save_message(chat_id, "assistant", response)

    # Feed episodic memory (Qdrant) with summary
    try:
        episode_summary = f"Usuário: {text[:200]}\nIARA: {response[:300]}"
        await memory.save_episode(episode_summary, chat_id)
    except Exception as e:
        logger.warning(f"⚠️ Episodic save failed: {e}")

    return {"response": response}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Conditional Routing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def route_by_intent(state: IaraState) -> str:
    """Conditional edge: route to the correct node based on semantic intent."""
    intent = str(state.get("intent", "chat_agent"))

    # Dynamic overrides from Dashboard
    settings = await settings_manager.get_settings()
    reasoning_mode = str(settings.get("reasoning_mode", "planning"))

    if intent == "tools_executor__deep_research":
        return "swarm_node"
    elif intent.startswith("tools_executor") or intent == "security__blocked":
        return "tools_node"
    elif intent == "council_debate":
        return "council_node" if reasoning_mode == "planning" else "memory_node"
    elif intent.startswith("swarm__"):
        return "swarm_node"
    else:
        # chat_agent, web_search fallback, deep_research, etc.
        return "memory_node"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Graph Assembly
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_graph() -> StateGraph:
    """
    Build the IARA brain graph:

        entry → router_node → ──┬─ tools_node ────────┬──→ formatter_node → END
                                 │                     │
                                 ├─ council_node ──────┤
                                 │                     │
                                 ├─ swarm_node ────────┤
                                 │                     │
                                 └─ memory_node → chat_node
    """
    graph = StateGraph(IaraState)

    # Add nodes
    graph.add_node("router_node", router_node)
    graph.add_node("memory_node", memory_node)
    graph.add_node("tools_node", tools_node)
    graph.add_node("council_node", council_node)
    graph.add_node("swarm_node", swarm_node)
    graph.add_node("chat_node", chat_node)
    graph.add_node("formatter_node", formatter_node)

    # Entry point
    graph.set_entry_point("router_node")

    # Conditional routing after intent classification
    graph.add_conditional_edges(
        "router_node",
        route_by_intent,
        {
            "tools_node": "tools_node",
            "council_node": "council_node",
            "swarm_node": "swarm_node",
            "memory_node": "memory_node",
        },
    )

    # Memory → Chat (sequential: load memory, then generate)
    graph.add_edge("memory_node", "chat_node")

    # All execution nodes → formatter
    graph.add_edge("tools_node", "formatter_node")
    graph.add_edge("council_node", "formatter_node")
    graph.add_edge("swarm_node", "formatter_node")
    graph.add_edge("chat_node", "formatter_node")

    # Formatter → END
    graph.add_edge("formatter_node", END)

    return graph


# Compile the graph once at module level
_compiled_graph = build_graph().compile()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public API (stable interface for main.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def process(text: str, chat_id: int) -> str:
    """
    Main brain entry point — invokes the LangGraph pipeline.
    Interface is identical to the old if/elif brain: process(text, chat_id) -> str
    """
    initial_state: IaraState = {
        "text": text,
        "chat_id": chat_id,
        "intent": "",
        "score": 0.0,
        "response": "",
        "core_facts": [],
        "episodes": [],
        "conversation": [],
        "task_type": "chat",
    }

    try:
        result = await _compiled_graph.ainvoke(initial_state)
        return result.get("response", "...")
    except Exception as e:
        logger.error(f"❌ LangGraph pipeline error: {e}", exc_info=True)
        return f"❌ Erro no pipeline: {str(e)[:200]}"
