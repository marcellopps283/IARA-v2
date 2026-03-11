"""
llm_router.py — Roteador multi-LLM com fallback automático
Usa aiohttp com a API REST compatível com OpenAI (sem SDK compilado).
Compatível com Termux/Android (sem jiter/C extensions).
"""

import asyncio
import json
import logging
import random
from typing import AsyncGenerator

import aiohttp
import datetime

import config
import hooks

logger = logging.getLogger("llm_router")

# Limita requisições LLM simultâneas (evita bans por HTTP 429 Timeouts)
_api_semaphore = asyncio.Semaphore(3)

# Controle estrito de cota diária
_daily_calls = 0
_current_day = datetime.date.today()

def check_and_increment_quota():
    global _daily_calls, _current_day
    today = datetime.date.today()
    if today != _current_day:
        _current_day = today
        _daily_calls = 0
        
    if _daily_calls >= config.MAX_DAILY_LLM_CALLS:
        raise RuntimeError(f"❌ [HITL POLICY] Cota diária estourada ({config.MAX_DAILY_LLM_CALLS} chamadas). Sistema bloqueado por segurança.")
    
    _daily_calls += 1


class LLMRouter:
    """
    Gerencia múltiplos provedores de LLM com fallback automático.
    
    Tenta o provedor primário (Groq). Se falhar (rate limit, timeout, erro),
    automaticamente tenta o próximo da lista. Suporta streaming.
    """

    def __init__(self):
        self.providers = []
        self._init_providers()
        self.current_provider = None

    def _init_providers(self):
        """Inicializa providers apenas com API key configurada."""
        for provider in config.LLM_PROVIDERS:
            if not provider["api_key"]:
                logger.info(f"⏭️ Provider '{provider['name']}' sem API key, pulando.")
                continue
            self.providers.append(provider)
            logger.info(f"✅ Provider '{provider['name']}' ({provider['model']}) configurado.")

        if not self.providers:
            raise RuntimeError("❌ Nenhum provider de LLM configurado! Verifique o .env")

    def _sort_providers_for_task(self, task_type: str, requires_tools: bool, require_fast: bool = False) -> list[dict]:
        """Ordena os provedores disponíveis baseando-se no tipo de tarefa, fallback e need for speed."""
        sorted_provs = []
        
        # Filtrar suporte a tools primeiro
        valid_provs = [p for p in self.providers if not (requires_tools and not p.get("supports_tools"))]
        
        if not valid_provs:
            # Fallback forçado se ninguém suportar e tools forem pedidas
            logger.warning(f"⚠️ Nenhum provider suporta tools para a task '{task_type}'. Ignorando requisito.")
            valid_provs = self.providers.copy()

        # Regras de Força Maior (Exclusividade)
        if task_type in ("vision", "embedding"):
            # Gemini é o único que suporta Visão nativa (Multimodal) e Embeddings no nosso setup
            valid_provs = [p for p in valid_provs if p["name"] == "gemini"]
            if not valid_provs:
                logger.error(f"❌ Tarefa '{task_type}' solicitada, mas Gemini não está configurado.")
            return valid_provs

        # Priorização baseada na especialidade
        for p in valid_provs:
            name = p["name"].lower()
            score = 0
            
            if task_type == "reasoning":
                # R1 reina em reasoning absoluto.
                if name == "openrouter": score = 10
                elif name.startswith("groq"): score = 8
                
            elif require_fast or task_type in ("intent", "consolidation", "chat_fast"):
                # Groq absoluto para fast. Se falhar as retries, o next na lista será OpenRouter.
                if name.startswith("groq"): score = 10
                elif name.startswith("cerebras"): score = 9
                elif name == "openrouter": score = 5 # Escalation fallback (DeepSeek R1)
                elif name == "gemini": score = 4
                
            elif task_type in ("code", "plan"):
                if name.startswith("groq"): score = 10
                elif name == "gemini": score = 8
                elif name == "mistral": score = 6              # Mistral Large como fallback
                elif name == "openrouter": score = 4           # Caso tools não importem tanto e a lógica falhe
                
            elif task_type == "research":
                if name == "kimi": score = 10         # Bom para lidar com grandes contextos
                elif name.startswith("groq"): score = 8
                elif name == "gemini": score = 7
                elif name == "openrouter": score = 6
                
            else: # "chat", "tools" e tarefas gerais
                if name.startswith("groq"): score = 10
                elif name == "gemini": score = 8
                elif name == "openrouter": score = 7
                elif name == "mistral": score = 6
                elif name == "kimi": score = 5
                
            sorted_provs.append((score, p))
            
        # Retorna ordenado do maior score pro menor
        sorted_provs.sort(key=lambda x: x[0], reverse=True)
        return [p for score, p in sorted_provs]

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        task_type: str = "chat",
        require_fast: bool = False,
        force_provider: str | None = None,
    ) -> str | dict:
        """
        Gera uma resposta usando o provider mais adequado para a tarefa.
        Se falhar, faz fallback para o próximo da lista ordenada.
        """
        check_and_increment_quota()
        
        # Hook de Segurança (Red Team): Ofuscar chaves/tokens
        for m in messages:
            if isinstance(m.get("content"), str):
                m["content"] = await hooks.before_submit_prompt(m["content"])

        last_error = None
        target_providers = self._sort_providers_for_task(task_type, bool(tools), require_fast=require_fast)
        if not target_providers and task_type == "vision":
            return "Visão não disponível: GEMINI_API_KEY ausente ou Gemini fora do ar. Descreva a imagem em texto."
            
        if force_provider:
            forced = [p for p in self.providers if p["name"] == force_provider]
            if forced:
                target_providers = forced
            else:
                logger.warning(f"⚠️ Provider '{force_provider}' não configurado. Ignorando force.")

        for provider in target_providers:
            try:
                logger.info(f"🧠 Tentando: {provider['name']} ({provider['model']})")
                self.current_provider = provider["name"]

                body = {
                    "model": provider["model"],
                    "messages": messages,
                    "max_tokens": provider["max_tokens"],
                    "temperature": temperature,
                    "stream": False,
                }

                if tools and provider.get("supports_tools"):
                    body["tools"] = tools
                    body["tool_choice"] = "auto"

                headers = {
                    "Authorization": f"Bearer {provider['api_key']}",
                    "Content-Type": "application/json",
                }

                url = f"{provider['base_url']}/chat/completions"
                timeout = aiohttp.ClientTimeout(total=config.LLM_TIMEOUT_SECONDS)

                max_retries = 2
                for attempt in range(max_retries):
                    async with _api_semaphore:
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            async with session.post(url, headers=headers, json=body) as resp:
                                if resp.status == 429:
                                    wait_time = (2 ** attempt) + random.uniform(0.1, 1.5)
                                    logger.warning(f"⚠️ {provider['name']}: Rate limit (429). Retry {attempt+1}/{max_retries} in {wait_time:.1f}s")
                                    if attempt < max_retries - 1:
                                        await asyncio.sleep(wait_time)
                                        continue
                                    else:
                                        break # Vai pro fallback (próximo provider)
                                        
                                if resp.status != 200:
                                    raw_err = await resp.text()
                                    error_text = str(raw_err)
                                    abbr_err = error_text[:200] if len(error_text) > 200 else error_text
                                    logger.warning(f"⚠️ {provider['name']}: HTTP {resp.status} - {abbr_err}")
                                    break # Erros normais não dão retry, fazemos fallback

                                data = await resp.json()

                                choice = data["choices"][0]
                                message = choice["message"]

                                # Se o modelo quer chamar tools
                                if choice.get("finish_reason") == "tool_calls" or message.get("tool_calls"):
                                    tool_call = message.get("tool_calls", [{}])[0]
                                    func = tool_call.get("function", {})
                                    name = func.get("name")
                                    args_str = func.get("arguments", "{}")
                                    try:
                                        args = json.loads(args_str)
                                    except Exception:
                                        args = {}
                                    return {"tool": name, "args": args}

                                return message.get("content", "")

            except asyncio.TimeoutError:
                logger.warning(f"⚠️ {provider['name']}: Timeout ({config.LLM_TIMEOUT_SECONDS}s)")
                last_error = f"Timeout em {provider['name']}"
                continue
            except Exception as e:
                err_str = str(e)
                abbr_err = err_str[:200] if len(err_str) > 200 else err_str
                logger.warning(f"⚠️ {provider['name']} falhou: {abbr_err}")
                last_error = err_str
                continue

        raise RuntimeError(f"❌ Todos os providers falharam. Último: {last_error}")

    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        task_type: str = "chat",
        require_fast: bool = False,
        force_provider: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Gera resposta em streaming (token por token via SSE).
        Faz fallback automático se o provider falhar.
        """
        check_and_increment_quota()
        
        target_providers = self._sort_providers_for_task(task_type, False, require_fast=require_fast)
        if not target_providers and task_type == "vision":
            yield "Visão não disponível: GEMINI_API_KEY ausente ou Gemini fora do ar. Descreva a imagem em texto."
            return
            
        if force_provider:
            forced = [p for p in self.providers if p["name"] == force_provider]
            if forced:
                target_providers = forced
            else:
                logger.warning(f"⚠️ Provider '{force_provider}' não configurado. Ignorando force.")
                
        last_error = None

        # Hook de Segurança (Red Team): Ofuscar chaves/tokens
        for m in messages:
            if isinstance(m.get("content"), str):
                m["content"] = await hooks.before_submit_prompt(m["content"])

        for provider in target_providers:
            if not provider.get("supports_streaming"):
                continue

            try:
                logger.info(f"🌊 Streaming via: {provider['name']} ({provider['model']})")
                self.current_provider = provider["name"]

                body = {
                    "model": provider["model"],
                    "messages": messages,
                    "max_tokens": provider["max_tokens"],
                    "temperature": temperature,
                    "stream": True,
                }

                headers = {
                    "Authorization": f"Bearer {provider['api_key']}",
                    "Content-Type": "application/json",
                }

                url = f"{provider['base_url']}/chat/completions"
                timeout = aiohttp.ClientTimeout(total=config.LLM_TIMEOUT_SECONDS)

                max_retries = 3
                for attempt in range(max_retries):
                    async with _api_semaphore:
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            async with session.post(url, headers=headers, json=body) as resp:
                                if resp.status == 429:
                                    wait_time = (2 ** attempt) + random.uniform(0.1, 1.5)
                                    logger.warning(f"⚠️ Streaming {provider['name']}: Rate limit (429). Retry {attempt+1}/{max_retries} in {wait_time:.1f}s")
                                    if attempt < max_retries - 1:
                                        await asyncio.sleep(wait_time)
                                        continue
                                    else:
                                        break # Vai pro fallback

                                if resp.status != 200:
                                    raw_err = await resp.text()
                                    error_text = str(raw_err)
                                    abbr_err = error_text[:200] if len(error_text) > 200 else error_text
                                    logger.warning(f"⚠️ Streaming {provider['name']}: HTTP {resp.status}")
                                    last_error = abbr_err
                                    break

                                # Parse SSE stream
                                async for line in resp.content:
                                    line = line.decode("utf-8").strip()
                                    if not line or not line.startswith("data: "):
                                        continue
                                    
                                    data_str = line[6:]  # Remove "data: "
                                    if data_str == "[DONE]":
                                        return

                                    try:
                                        data = json.loads(data_str)
                                        delta = data["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                    except (json.JSONDecodeError, KeyError, IndexError):
                                        continue

                return  # Stream completou

            except Exception as e:
                err_str = str(e)
                abbr_err = err_str[:200] if len(err_str) > 200 else err_str
                logger.warning(f"⚠️ Streaming '{provider['name']}' falhou: {abbr_err}")
                last_error = err_str
                continue

        # Se streaming falhou, tenta sem stream
        logger.warning("⚠️ Streaming falhou em todos, tentando sem stream...")
        try:
            result = await self.generate(messages, temperature=temperature)
            if isinstance(result, str):
                yield result
        except Exception as e:
            yield f"😿 Desculpa Criador, todos os meus cérebros falharam. Erro: {str(e)[:100]}"

    def get_status(self) -> dict:
        """Retorna status dos providers configurados."""
        return {
            "providers_ativos": [p["name"] for p in self.providers],
            "provider_atual": self.current_provider,
            "total_providers": len(self.providers),
        }
