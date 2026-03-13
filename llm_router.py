"""
llm_router.py — SOTA 2026 LiteLLM Gateway Client
Delegates all LLM orchestration to the LiteLLM Proxy.
Proactive rate-limiting, semantic cache, and multi-provider fallback 
are handled centrally via litellm_config.yaml.
"""

import json
import asyncio
import datetime
import logging
from typing import AsyncGenerator, Any
import os

import aiohttp
import config
import hooks

logger = logging.getLogger("llm_router")

# LiteLLM Proxy URL (Docker internal or localhost fallback)
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000/chat/completions")

class LLMRouter:
    """
    Client for LiteLLM Gateway. 
    Simplifies IARA core logic while gaining enterprise-grade features.
    """

    def __init__(self):
        self.current_provider = "litellm-gateway"

    def _get_model_for_task(self, task_type: str) -> str:
        """Maps IARA task types to LiteLLM model identifiers."""
        mapping = {
            "reasoning": "minimax-m2.5",            # SOTA Reasoning MoE
            "fast": "groq-llama-3.1-70b",           # Ultra-fast Groq
            "intent": "groq-llama-3.1-70b",
            "consolidation": "groq-llama-3.1-70b",
            "code": "qwen-coder-dashscope",         # Specialized Coder
            "plan": "qwen-coder-dashscope",
            "research": "zhipu-glm-4-flash",        # 200k Context Window
            "vision": "gemini-2.0-flash",           # Native Multimodal
            "audit": "github-models-o1",            # High-stakes audit (SOTA 2026)
        }
        return mapping.get(task_type, "gemini-2.0-flash") # Robust fallback

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        task_type: str = "chat",
        force_model: str | None = None,
        **kwargs
    ) -> str | dict:
        """Primary generation method using LiteLLM Proxy."""
        
        # 🛡️ Security Hook
        for m in messages:
            if isinstance(m.get("content"), str):
                m["content"] = await hooks.before_submit_prompt(m["content"])

        model = force_model or self._get_model_for_task(task_type)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.info(f"🧠 LiteLLM Req: {model} [Task: {task_type}]")
        
        start_time = datetime.datetime.now()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(LITELLM_URL, json=payload, timeout=config.LLM_TIMEOUT_SECONDS) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(f"❌ LiteLLM Error ({resp.status}): {err_text[:500]}")
                        raise RuntimeError(f"Gateway Error: {resp.status}")

                    data = await resp.json()
                    duration = (datetime.datetime.now() - start_time).total_seconds() * 1000
                    logger.info(f"⚡ Latency (via LiteLLM): {duration:.1f}ms")

                    choice = data["choices"][0]
                    message = choice["message"]

                    # Handle Tool Calls
                    if message.get("tool_calls"):
                        tool_call = message["tool_calls"][0]
                        func = tool_call["function"]
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except Exception:
                            args = {}
                        return {"tool": func["name"], "args": args}

                    return message.get("content", "")
            except Exception as e:
                logger.error(f"❌ Gateway Connection Failed: {e}")
                raise

    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        task_type: str = "chat",
        force_model: str | None = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Streaming generation via LiteLLM Proxy (SSE)."""
        
        # 🛡️ Security Hook
        for m in messages:
            if isinstance(m.get("content"), str):
                m["content"] = await hooks.before_submit_prompt(m["content"])

        model = force_model or self._get_model_for_task(task_type)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        logger.info(f"🌊 LiteLLM Stream: {model}")
        
        start_time = datetime.datetime.now()
        first_token = False

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(LITELLM_URL, json=payload) as resp:
                    if resp.status != 200:
                        yield f"❌ Gateway Error: {resp.status}"
                        return

                    async for line in resp.content:
                        if not first_token:
                            ttft = (datetime.datetime.now() - start_time).total_seconds() * 1000
                            logger.info(f"⚡ TTFT (via LiteLLM): {ttft:.1f}ms")
                            first_token = True

                        line_str = line.decode("utf-8").strip()
                        if not line_str.startswith("data: "):
                            continue
                        
                        data_raw = line_str[6:]
                        if data_raw == "[DONE]":
                            break

                        try:
                            data = json.loads(data_raw)
                            content = data["choices"][0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except:
                            continue
            except Exception as e:
                logger.error(f"❌ Stream Failure: {e}")
                yield f"⚠️ Conexão com o Cérebro perdida (Gateway offline)."

    def get_status(self) -> dict:
        return {
            "provider": "LiteLLM Gateway",
            "endpoint": LITELLM_URL,
            "status": "active"
        }
