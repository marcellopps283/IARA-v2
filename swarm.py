"""
swarm.py — Specialist Agent Swarm for IARA
MoE (Mixture of Experts) pattern: the brain delegates tasks to specialist agents,
each with their own system prompt, tools, and preferred LLM provider.

Architecture:
    Brain → classify task → dispatch to specialist → specialist calls LLM → return result
"""

import logging
from dataclasses import dataclass, field

from llm_router import LLMRouter

logger = logging.getLogger("swarm")


@dataclass
class Specialist:
    """Defines a specialist agent with its own identity and capabilities."""
    name: str
    role: str
    system_prompt: str
    preferred_task_type: str = "chat"  # maps to LLMRouter task types
    temperature: float = 0.7
    max_tokens: int = 4096


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Specialist Definitions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CODER = Specialist(
    name="Coder",
    role="💻 Desenvolvedor",
    system_prompt="""Você é o Coder, o especialista em programação da IARA.

REGRAS:
- Escreva código limpo, comentado e funcional
- Use Python a menos que o usuário peça outra linguagem
- Sempre inclua tratamento de erros
- Se o código for longo, divida em funções claras
- Forneça exemplos de uso quando relevante
- Responda em português brasileiro""",
    preferred_task_type="code",
    temperature=0.3,
)

RESEARCHER = Specialist(
    name="Researcher",
    role="🔍 Pesquisador",
    system_prompt="""Você é o Researcher, o especialista em pesquisa e análise da IARA.

REGRAS:
- Seja extremamente detalhado e preciso
- Cite fontes quando disponíveis
- Organize a resposta com headers e bullet points
- Apresente múltiplas perspectivas quando relevante
- Se não souber algo, diga explicitamente
- Responda em português brasileiro""",
    preferred_task_type="reasoning",
    temperature=0.5,
)

PLANNER = Specialist(
    name="Planner",
    role="📋 Planejador",
    system_prompt="""Você é o Planner, o especialista em planejamento e arquitetura da IARA.

REGRAS:
- Decomponha problemas complexos em etapas claras
- Use checklists e diagramas quando útil
- Considere riscos e dependências
- Proponha alternativas (Plano A, B)
- Estime esforço e prioridades
- Responda em português brasileiro""",
    preferred_task_type="reasoning",
    temperature=0.4,
)

CREATIVE = Specialist(
    name="Creative",
    role="🎨 Criativo",
    system_prompt="""Você é o Creative, o especialista criativo da IARA.

REGRAS:
- Pense fora da caixa, sugira abordagens inovadoras
- Use analogias e metáforas para explicar conceitos
- Seja envolvente e inspirador
- Proponha soluções criativas para problemas
- Responda em português brasileiro""",
    preferred_task_type="chat",
    temperature=0.9,
)

# Registry of all specialists
SPECIALISTS: dict[str, Specialist] = {
    "coder": CODER,
    "researcher": RESEARCHER,
    "planner": PLANNER,
    "creative": CREATIVE,
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dispatch
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_router: LLMRouter | None = None


def _get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


async def dispatch(specialist_name: str, task: str, context: str = "") -> str:
    """
    Dispatch a task to a single specialist agent.
    Returns the specialist's response.
    """
    spec = SPECIALISTS.get(specialist_name.lower())
    if not spec:
        return f"❌ Especialista '{specialist_name}' não encontrado."

    logger.info(f"🐝 Dispatching to {spec.role} ({spec.name})...")

    messages = [
        {"role": "system", "content": spec.system_prompt},
    ]
    if context:
        messages.append({"role": "system", "content": f"[CONTEXTO]\n{context}"})
    messages.append({"role": "user", "content": task})

    router = _get_router()
    try:
        response = await router.generate(
            messages=messages,
            task_type=spec.preferred_task_type,
            temperature=spec.temperature,
        )
        return response or "..."
    except Exception as e:
        logger.error(f"❌ Specialist {spec.name} failed: {e}")
        return f"❌ {spec.role} falhou: {e}"


async def dispatch_parallel(specialist_names: list[str], task: str, context: str = "") -> str:
    """
    Dispatch a task to multiple specialists simultaneously (MoA pattern).
    Returns a unified response combining all their outputs.
    """
    import asyncio
    
    valid_names = [name for name in specialist_names if name.lower() in SPECIALISTS]
    if not valid_names:
        return "❌ Nenhum especialista válido fornecido para execução paralela."

    logger.info(f"🐝🚀 Parallel dispatch to: {', '.join(valid_names)}")
    
    # Run all specialists concurrently with a timeout
    async def _run_one(name: str):
        try:
            return await asyncio.wait_for(dispatch(name, task, context), timeout=60.0)
        except asyncio.TimeoutError:
            return f"❌ Especialista {name} expirou (timeout 60s)."
        except Exception as e:
            return f"❌ Especialista {name} falhou: {e}"

    results = await asyncio.gather(*[_run_one(name) for name in valid_names])
    
    # Combine results
    combined = []
    for name, result in zip(valid_names, results):
        spec = SPECIALISTS.get(name.lower())
        role_title = spec.role if spec else name
        combined.append(f"### {role_title}\n{result}\n")
        
    return "\n".join(combined)


