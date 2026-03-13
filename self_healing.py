"""
self_healing.py — IARA Meta-Cognition & Recovery Module
Handles state rectification when execution confidence is low.
"""

import logging
import json
import config
from typing import Any

logger = logging.getLogger("self_healing")

async def heal_state(state: Any) -> dict:
    """
    Analyzes the low-confidence state and rewrites the task to try a different path.
    """
    from brain import get_router
    router = get_router()
    
    last_text = state.get("text", "")
    last_response = state.get("response", "")
    intent = state.get("intent", "unknown")
    confidence = state.get("confidence", 0.0)
    
    logger.info(f"🔧 Self-Healing triggered for intent '{intent}' (Confidence: {confidence:.2f})")
    
    # 1. Meta-Cognitive Analysis
    # We ask a reasoning model to analyze why it failed and suggest a "correction prompt"
    analysis_prompt = f"""
    SISTEMA IARA - Módulo de Meta-Cognição (Fase 15)
    
    A execução anterior falhou ou teve baixa confiança.
    Entrada do Usuário: {last_text}
    Intenção Identificada: {intent}
    Saída/Erro da ferramenta: {last_response}
    Confiança: {confidence}
    
    Analise o erro. O que deu errado? (ex: bug no código, site inacessível, falta de contexto).
    Crie uma NOVA instrução curta e direta para o sistema tentar resolver o problema por outro caminho.
    Se o erro foi de código, sugira uma abordagem mais simples.
    Se o erro foi de leitura de site, sugira buscar no Google/DuckDuckGo em vez de ler a URL direta.
    
    Responda no formato JSON:
    {{
        "reason": "explicação curta do erro",
        "new_instruction": "a nova instrução para a IARA",
        "blacklist_tool": "nome_da_ferramenta_se_deve_ser_evitada"
    }}
    """
    
    try:
        response = await router.generate(
            [{"role": "user", "content": analysis_prompt}],
            task_type="fast" # Use fast/coder for meta-analysis
        )
        # Handle string response (router might return dict if tool choice, but here we expect text)
        if isinstance(response, dict):
            # This shouldn't happen for this prompt, but let's be safe
            response = str(response)
            
        # Extract JSON from response
        # Sometimes markdown blocks are returned
        json_match = response.replace("```json", "").replace("```", "").strip()
        analysis = json.loads(json_match)
        
        reason = analysis.get("reason", "Erro indefinido")
        new_instruction = analysis.get("new_instruction", last_text)
        
        logger.info(f"💡 Healing Plan: {reason}")
        
        # 2. Rectify State
        # We append the failure information to the conversation so the next node knows what failed
        healing_message = f"⚠️ [Self-Healing] Tentativa anterior falhou: {reason}. Nova estratégia: {new_instruction}"
        
        # Return updates for the state
        return {
            "text": f"{new_instruction} (Obs: a tentativa anterior falhou por: {reason})",
            "confidence": 0.5, # Reset confidence marginally to avoid infinite loop
            "response": healing_message
        }
        
    except Exception as e:
        logger.error(f"❌ Self-healing failed to generate plan: {e}")
        # Fallback: simple retry instruction
        return {
            "text": f"Tente novamente com uma abordagem diferente para: {last_text}",
            "confidence": 0.5
        }
