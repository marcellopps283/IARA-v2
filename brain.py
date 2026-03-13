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
from typing import TypedDict, AsyncGenerator, cast, Any

from langgraph.graph import StateGraph, END
from langgraph.types import Send

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
    core_facts: Any              # From Postgres/Mem0 (permanent memory)
    episodes: Any                # From Qdrant/Mem0 (episodic memory)
    kg_context: str              # From LightRAG (Knowledge Graph)
    conversation: Any            # From Redis (working memory)
    task_type: str               # For LLM router prioritization
    _stream_queue: Any           # Internal: For SSE streaming (SOTA 2026)
    specialist: str              # For specialist_node routing
    confidence: float            # For autonomous audit triggers (SOTA 2026)


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


def build_system_prompt(
    core_facts: list[dict] | None = None, 
    episodes: list[str] | None = None, 
    kg_context: str | None = None
) -> str:
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
    if kg_context and kg_context.strip():
        memory_section += f"\n\n[GRAFO DE CONHECIMENTO — Contexto profundo]\n{kg_context}"

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
    """
    Load memory layers in parallel (SOTA 2026 Parallel Fetch).
    Fetches Core Facts, Episodes, Knowledge Graph and Conversation history.
    """
    import memory_manager
    text = state["text"]
    chat_id = state["chat_id"]

    # Parallel Fetch with return_exceptions=True to prevent total failure if one backend is down
    results = await asyncio.gather(
        memory.get_core_facts(limit=5),
        memory.search_episodes(text, chat_id=chat_id, limit=3),
        memory_manager.search_knowledge_graph(text),
        memory.get_conversation(chat_id),
        return_exceptions=True
    )

    core_facts = results[0] if not isinstance(results[0], Exception) else []
    episodes = results[1] if not isinstance(results[1], Exception) else []
    kg_context = results[2] if not isinstance(results[2], Exception) else ""
    conversation = results[3] if not isinstance(results[3], Exception) else []

    if any(isinstance(r, Exception) for r in results):
        logger.warning(f"⚠️ Some memory backends failed: {[r for r in results if isinstance(r, Exception)]}")

    return {
        "core_facts": core_facts,
        "episodes": episodes,
        "kg_context": kg_context,
        "conversation": conversation,
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
        
        if result.get("exit_code") == 0 and result.get("confidence", 0) >= 0.85:
            response = (
                f"✅ **REDCODER (gVisor 2026)**\n\n"
                f"**Output:**\n```\n{stdout}\n```\n\n"
                f"*Resolvido em {iters} iteração(ões) com isolamento total.*"
            )
            return {"response": response, "confidence": result.get("confidence", 1.0)}
        else:
            # If code failed or logic is shaky, we set the response and let the audit_router handle it
            response = stdout if result.get("exit_code") == 0 else stderr
            return {"response": response, "confidence": result.get("confidence", 0.0)}

    # ── URL reading ──

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
    
    # Council with Streaming support (SOTA 2026)
    stream_queue = state.get("_stream_queue")
    if stream_queue:
        q = cast(Any, stream_queue)
        await q.put("⚖️ **Iniciando debate no Conselho...**\n\n")
        response = await council.debate(text, context=str(state.get("conversation", [])))
        await q.put(response)
        return {"response": response}

    logger.info("⚖️ Invoking Council debate...")
    response = await council.debate(text, context=str(state.get("conversation", [])))
    return {"response": response}


async def specialist_node(state: IaraState) -> dict:
    """Dispatch to a Swarm specialist (Coder, Researcher, Planner, Creative)."""
    text = state["text"]
    chat_id = state["chat_id"]
    specialist = state.get("specialist", "researcher") # Passed via Send

    logger.info(f"🐝 Specialist Node: {specialist}")

    conversation = await memory.get_conversation(chat_id)
    # Cast to Any to bypass checker slice indexing issues
    history = cast(Any, list(conversation) if conversation else [])
    history_slice = history[-6:]
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
        kg_context=state.get("kg_context")
    )

    messages = [{"role": "system", "content": system_prompt}]
    # Add conversation history
    conv = state.get("conversation", [])
    messages.extend(cast(Any, conv))

    active_model = await settings_manager.get_active_model()
    
    r = get_router()
    try:
        stream_queue = state.get("_stream_queue")
        
        # If streaming is requested, iterate over the stream
        if stream_queue:
            import typing
            q = typing.cast(asyncio.Queue, stream_queue)
            full_response = ""
            async for token in r.generate_stream(
                messages=messages, 
                task_type=task_type,
                force_model=active_model
            ):
                full_response += token
                await q.put(token)
            
            return {"response": full_response}

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

async def route_by_intent(state: IaraState) -> str | list[Send]:
    """Conditional edge: route to the correct node or Send to specialist."""
    intent = str(state.get("intent", "chat_agent"))
    
    # Dashboard Overrides
    settings = await settings_manager.get_settings()
    reasoning_mode = str(settings.get("reasoning_mode", "planning"))

    if intent == "tools_executor__deep_research":
        return [Send("specialist_node", {**state, "specialist": "researcher"})]
    elif intent.startswith("swarm__"):
        specialist = intent.replace("swarm__", "")
        return [Send("specialist_node", {**state, "specialist": specialist})]
    elif intent == "council_debate":
        return "council_node" if reasoning_mode == "planning" else "memory_node"
    elif intent.startswith("tools_executor") or intent == "security__blocked":
        return "tools_node"
    else:
        return "memory_node"


async def audit_router(state: IaraState) -> str:
    """Reroutes to audit_node if confidence is low."""
    confidence = state.get("confidence", 1.0)
    if confidence < 0.85:
        logger.warning(f"🛡️ Low confidence ({confidence:.2f}) detected. Routing to Audit Node.")
        return "audit_node"
    return "formatter_node"


async def audit_node(state: IaraState) -> dict:
    """
    SOTA 2026 Audit Node.
    Uses high-precision reasoning (o1) to validate critical outputs or security-sensitive code.
    """
    text = state["text"]
    response_to_audit = state.get("response", "")
    
    prompt = f"""
    AUDITORIA DE SEGURANÇA IARA v2
    Usuário: {text}
    Resposta Gerada: {response_to_audit}
    
    Sua tarefa é garantir que a resposta acima não contenha segredos vazados, 
    código malicioso ou instruções que violem as leis da robótica (e do bom senso).
    Se estiver TUDO OK, retorne apenas o texto original.
    Se houver problemas, retorne uma versão corrigida ou um aviso de segurança.
    """
    
    r = get_router()
    audited_response = await r.generate(
        messages=[{"role": "user", "content": prompt}],
        task_type="audit"
    )
    
    return {"response": audited_response}


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
                                 ├─ specialist_node ────────┤
                                 │                     │
                                 └─ memory_node → chat_node
    """
    graph = StateGraph(IaraState)

    # Add nodes
    graph.add_node("router_node", router_node)
    graph.add_node("memory_node", memory_node)
    graph.add_node("tools_node", tools_node)
    graph.add_node("council_node", council_node)
    graph.add_node("specialist_node", specialist_node)
    graph.add_node("chat_node", chat_node)
    graph.add_node("audit_node", audit_node)
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
            "specialist_node": "specialist_node",
            "memory_node": "memory_node",
            "audit_node": "audit_node",
        },
    )

    # Memory → Chat (sequential: load memory, then generate)
    graph.add_edge("memory_node", "chat_node")

    # Execution nodes flow to audit_router first
    graph.add_conditional_edges("tools_node", audit_router, {"audit_node": "audit_node", "formatter_node": "formatter_node"})
    graph.add_conditional_edges("council_node", audit_router, {"audit_node": "audit_node", "formatter_node": "formatter_node"})
    graph.add_conditional_edges("specialist_node", audit_router, {"audit_node": "audit_node", "formatter_node": "formatter_node"})
    graph.add_conditional_edges("chat_node", audit_router, {"audit_node": "audit_node", "formatter_node": "formatter_node"})
    
    # Audit Node always goes to formatter
    graph.add_edge("audit_node", "formatter_node")

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
        "kg_context": "",
        "conversation": [],
        "task_type": "chat",
        "_stream_queue": None,
        "confidence": 1.0,
    }

    try:
        result = await _compiled_graph.ainvoke(initial_state)
        return result.get("response", "...")
    except Exception as e:
        logger.error(f"❌ LangGraph pipeline error: {e}", exc_info=True)
        return f"❌ Erro no pipeline: {str(e)[:200]}"


async def process_stream(text: str, chat_id: int) -> AsyncGenerator[str, None]:
    """
    SOTA 2026 Streaming Entry Point.
    Returns an AsyncGenerator that yields tokens directly from LLM nodes.
    """
    token_queue = asyncio.Queue()
    
    initial_state: IaraState = {
        "text": text,
        "chat_id": chat_id,
        "intent": "",
        "score": 0.0,
        "response": "",
        "core_facts": [],
        "episodes": [],
        "kg_context": "",
        "conversation": [],
        "task_type": "chat",
        "_stream_queue": token_queue,
        "confidence": 1.0,
    }

    # Run the graph in a separate task
    async def run_graph():
        try:
            await _compiled_graph.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"❌ Streaming Graph failed: {e}")
            await token_queue.put(f"\n\n❌ [ERRO]: {str(e)}")
        finally:
            # Sentinel value to signal end of stream
            if token_queue:
                await token_queue.put(None)

    graph_task = asyncio.create_task(run_graph())

    # Yield tokens as they arrive
    while True:
        token = await token_queue.get()
        if token is None:
            break
        yield token

    await graph_task
