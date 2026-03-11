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
    Dispatch a task to a specialist agent.
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


def detect_specialist(text: str) -> str | None:
    """
    Auto-detect which specialist should handle this task.
    Returns specialist name or None for general chat.
    """
    text_lower = text.lower()

    # Code-related keywords
    code_kw = ["código", "codigo", "função", "funcao", "classe", "debug",
               "bug", "erro no código", "implementa", "programa", "script",
               "refatora", "refactor", "api", "endpoint", "docker", "git"]
    for kw in code_kw:
        if kw in text_lower:
            return "coder"

    # Research keywords
    research_kw = ["pesquisa aprofundada", "artigo", "paper", "estudo",
                   "compare", "diferença entre", "prós e contras",
                   "análise detalhada", "analise detalhada"]
    for kw in research_kw:
        if kw in text_lower:
            return "researcher"

    # Planning keywords
    plan_kw = ["planeje", "plano", "roadmap", "cronograma", "milestone",
               "desenhe a arquitetura", "estratégia", "etapas para"]
    for kw in plan_kw:
        if kw in text_lower:
            return "planner"

    # Creative keywords
    creative_kw = ["crie", "invente", "imagine", "história", "estória",
                   "ideia para", "brainstorm", "nome para"]
    for kw in creative_kw:
        if kw in text_lower:
            return "creative"

    return None
