"""
council.py — Adversarial Council for IARA
Implements the Blue Team vs Red Team debate pattern for critical decisions.

Flow:
    1. Blue Team (Builder) proposes a solution
    2. Red Team (Breaker) critiques and finds weaknesses
    3. Synthesis: merge the best of both into a final answer
"""

import logging

from llm_router import LLMRouter

logger = logging.getLogger("council")

_router: LLMRouter | None = None


def _get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


BLUE_TEAM_PROMPT = """Você é o Blue Team (Construtor) da IARA.
Seu papel é PROPOR a melhor solução possível para o problema apresentado.
Seja detalhado, técnico e construtivo. Apresente sua proposta de forma clara e organizada.
Responda em português brasileiro."""

RED_TEAM_PROMPT = """Você é o Red Team (Destruidor) da IARA.
Seu papel é CRITICAR e encontrar FALHAS na proposta apresentada.
Seja rigoroso mas justo. Aponte:
- Pontos cegos e edge cases não cobertos
- Riscos de segurança ou performance
- Alternativas melhores
- O que acontece quando as coisas dão errado
Responda em português brasileiro."""

SYNTHESIS_PROMPT = """Você é a IARA, sintetizando um debate entre Blue Team e Red Team.
Analise ambos os argumentos e produza a MELHOR RESPOSTA POSSÍVEL combinando:
- Os pontos fortes da proposta do Blue Team
- As correções válidas do Red Team
- Sua própria perspectiva como juíza

Formato da resposta:
⚖️ **Síntese do Conselho**
[Sua resposta final integrada]

📊 **Scorecard**
- Blue Team: [X/10] - [breve justificativa]
- Red Team: [X/10] - [breve justificativa]

Responda em português brasileiro."""


async def debate(topic: str, context: str = "") -> str:
    """
    Run a full council debate on a topic.
    Returns the synthesized result.
    """
    router = _get_router()
    logger.info(f"⚖️ Council debate started: {topic[:60]}...")

    # Round 1: Blue Team proposes
    blue_messages = [
        {"role": "system", "content": BLUE_TEAM_PROMPT},
    ]
    if context:
        blue_messages.append({"role": "system", "content": f"[CONTEXTO]\n{context}"})
    blue_messages.append({"role": "user", "content": f"Proponha uma solução para: {topic}"})

    try:
        blue_response = await router.generate(
            messages=blue_messages,
            task_type="reasoning",
            temperature=0.6,
        )
        logger.info(f"🔵 Blue Team responded ({len(blue_response or '')} chars)")
    except Exception as e:
        logger.error(f"❌ Blue Team failed: {e}")
        return f"❌ O Council falhou na fase Blue Team: {e}"

    # Round 2: Red Team critiques
    red_messages = [
        {"role": "system", "content": RED_TEAM_PROMPT},
        {"role": "user", "content": f"Analise criticamente esta proposta:\n\n{blue_response}\n\nPergunta original: {topic}"},
    ]

    try:
        red_response = await router.generate(
            messages=red_messages,
            task_type="reasoning",
            temperature=0.7,
        )
        logger.info(f"🔴 Red Team responded ({len(red_response or '')} chars)")
    except Exception as e:
        logger.error(f"❌ Red Team failed: {e}")
        # If Red Team fails, return only Blue Team's response
        return f"🔵 **Blue Team (sem revisão):**\n\n{blue_response}"

    # Round 3: Synthesis
    synthesis_messages = [
        {"role": "system", "content": SYNTHESIS_PROMPT},
        {"role": "user", "content": f"""Pergunta original: {topic}

🔵 **Proposta do Blue Team:**
{blue_response}

🔴 **Crítica do Red Team:**
{red_response}

Sintetize a melhor resposta combinando ambas as perspectivas."""},
    ]

    try:
        synthesis = await router.generate(
            messages=synthesis_messages,
            task_type="reasoning",
            temperature=0.5,
        )
        logger.info(f"⚖️ Synthesis complete ({len(synthesis or '')} chars)")
        return synthesis or "..."
    except Exception as e:
        logger.error(f"❌ Synthesis failed: {e}")
        return f"🔵 **Blue Team:**\n{blue_response}\n\n🔴 **Red Team:**\n{red_response}\n\n⚠️ Síntese automática falhou."


def should_use_council(text: str) -> bool:
    """Detect if the topic warrants a full council debate."""
    text_lower = text.lower()

    council_triggers = [
        "conselho", "council", "debate",
        "analise criticamente", "analisa criticamente",
        "prós e contras", "pros e contras",
        "devo ou não", "vale a pena",
        "compare as opções", "qual a melhor abordagem",
        "blue team", "red team",
        "decisão importante", "decisão crítica",
        "arquitetura ideal", "convoca o conselho",
    ]

    return any(kw in text_lower for kw in council_triggers)
