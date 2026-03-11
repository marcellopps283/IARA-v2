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
    Layer 1: Blue + Red run in PARALLEL (MoA pattern).
    Layer 2: Synthesis merges both outputs.
    Each call has a 45-second timeout.
    """
    import asyncio
    router = _get_router()
    logger.info(f"⚖️ Council debate started: {topic[:60]}...")

    LLM_TIMEOUT = 45  # seconds per LLM call

    # Build messages for both teams
    blue_messages = [
        {"role": "system", "content": BLUE_TEAM_PROMPT},
    ]
    if context:
        blue_messages.append({"role": "system", "content": f"[CONTEXTO]\n{context}"})
    blue_messages.append({"role": "user", "content": f"Proponha uma solução para: {topic}"})

    red_messages = [
        {"role": "system", "content": RED_TEAM_PROMPT},
        {"role": "user", "content": f"Analise criticamente este tema e encontre falhas em possíveis soluções:\n\n{topic}"},
    ]

    # Layer 1: Blue + Red in parallel (MoA)
    async def _blue():
        return await asyncio.wait_for(
            router.generate(messages=blue_messages, task_type="reasoning", temperature=0.6),
            timeout=LLM_TIMEOUT,
        )

    async def _red():
        return await asyncio.wait_for(
            router.generate(messages=red_messages, task_type="reasoning", temperature=0.7),
            timeout=LLM_TIMEOUT,
        )

    blue_response, red_response = None, None
    try:
        results = await asyncio.gather(_blue(), _red(), return_exceptions=True)

        if isinstance(results[0], Exception):
            logger.error(f"❌ Blue Team failed: {results[0]}")
            blue_response = None
        else:
            blue_response = results[0]
            logger.info(f"🔵 Blue Team responded ({len(blue_response or '')} chars)")

        if isinstance(results[1], Exception):
            logger.error(f"❌ Red Team failed: {results[1]}")
            red_response = None
        else:
            red_response = results[1]
            logger.info(f"🔴 Red Team responded ({len(red_response or '')} chars)")

    except Exception as e:
        logger.error(f"❌ Council Layer 1 failed: {e}")
        return f"❌ O Council falhou: {e}"

    # Fallbacks if one team failed
    if not blue_response and not red_response:
        return "❌ Ambos os times falharam. Tente novamente."
    if not blue_response:
        return f"🔴 **Red Team (sem proposta Blue):**\n\n{red_response}"
    if not red_response:
        return f"🔵 **Blue Team (sem revisão Red):**\n\n{blue_response}"

    # Layer 2: Synthesis
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
        synthesis = await asyncio.wait_for(
            router.generate(messages=synthesis_messages, task_type="reasoning", temperature=0.5),
            timeout=LLM_TIMEOUT,
        )
        logger.info(f"⚖️ Synthesis complete ({len(synthesis or '')} chars)")
        return synthesis or "..."
    except asyncio.TimeoutError:
        logger.error("❌ Synthesis timed out")
        return f"🔵 **Blue Team:**\n{blue_response}\n\n🔴 **Red Team:**\n{red_response}\n\n⚠️ Síntese expirou (timeout {LLM_TIMEOUT}s)."
    except Exception as e:
        logger.error(f"❌ Synthesis failed: {e}")
        return f"🔵 **Blue Team:**\n{blue_response}\n\n🔴 **Red Team:**\n{red_response}\n\n⚠️ Síntese automática falhou."


