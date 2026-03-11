"""
brain.py — Orquestrador principal da Iara
Ponto de entrada: recebe mensagem → classifica intent → executa tools → chama LLM → responde.
"""

import asyncio
import json
import logging
import re
import sys
import base64
import mimetypes
import os
from datetime import datetime, timedelta
import hooks

# Configurar logging antes de importar módulos
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("brain")

import config
import core
import tools_registry
import scheduler
import web_search
import deep_research
import doc_reader
import telegram_bot
import worker_protocol
from llm_router import LLMRouter

import threading
import dashboard_api
import orchestrator
import mcp_client
import re


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Intent Detection — classifica o que o Criador quer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INTENT_CHAT = "chat"
INTENT_TOOL = "tool"
INTENT_RESEARCH = "deep_research"
INTENT_IGNORE = "ignore"
INTENT_COUNCIL = "council"

SEARCH_KEYWORDS = [
    "pesquisa", "pesquisar", "busca", "buscar", "procura", "procurar",
    "search", "google", "qual o preço", "quanto custa",
    "quanto tá", "quanto está", "cotação",
    "notícia", "noticias", "news",
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

WEATHER_KEYWORDS = [
    "clima", "tempo", "previsão", "vai chover", "temperatura",
    "tá frio", "tá quente", "weather", "chovendo",
]

STATUS_KEYWORDS = [
    "status", "bateria", "battery", "storage", "como tá o celular",
    "espaço", "sistema", "uptime",
]

REMINDER_KEYWORDS = [
    "me lembra", "me lembre", "me avisa", "me avise",
    "daqui a", "daqui", "lembrete", "reminder",
    "me acorda", "alarme",
]

DEEP_RESEARCH_KEYWORDS = [
    "pesquisa profunda", "pesquisa detalhada", "deep search",
    "deep research", "pesquisa completa", "analisa profundamente",
    "faz um levantamento", "investiga sobre", "investigar sobre",
    "pesquisa tudo sobre",
]

SWARM_KEYWORDS = [
    "swarm", "no swarm", "joga no swarm", "pede pro swarm",
    "manda um agente", "cria um agente", "delega pra",
    "revisa esse código", "analisa esse log",
]

CYBER_HANDS_KEYWORDS = [
    "lanterna", "ligar lanterna", "apagar lanterna", "desligar lanterna",
    "luz", "ilumina", "onde eu to", "onde eu tô", "localização",
    "localizacao", "onde nós estamos", "gps", "coordenadas",
]

# Verbos e Termos que engatilham a Complexidade Semântica (Escalation pro R1)
REASONING_KEYWORDS = [
    "aprofunde", "aprofunda", "detalha", "detalhe", "explique detalhadamente",
    "refatora", "refatore", "analisa criticamente", "analise criticamente",
    "pense passo a passo", "pense bem", "complexo", "crie uma arquitetura",
    "avalie as opções", "pense como especialista"
]

COUNCIL_KEYWORDS = ["conselho", "opiniões", "debate", "reunião", "votação", "analisem", "perspectivas"]
SANDBOX_KEYWORDS = ["sandbox", "e2b", "nuvem", "cloud", "gráfico", "plot", "code interpreter"]

# Regex para detectar URLs
URL_REGEX = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

# Regex para detectar Imagens Anexadas (Vision)
VISION_REGEX = re.compile(r"\[Imagem Anexada:\s*(.+?)\]")


def hydrate_vision_payload(messages: list[dict]) -> tuple[list[dict], bool]:
    """
    Substitui as tags de imagens lógicas pelos arrays Base64 formatados para OpenAI Vision.
    Apenas hidrata as imagens presentes nas últimas 2 mensagens para evitar estouro de tokens.
    Imagens antigas são substituídas por um texto descritivo simples.
    Retorna (mensagens_hidratadas, has_vision).
    """
    hydrated = []
    has_vision = False
    
    # Define limiar para considerar como "recente" (apenas as últimas 2 mensagens do array)
    recent_threshold = len(messages) - 2

    for i, msg in enumerate(messages):
        if not isinstance(msg.get("content"), str):
            hydrated.append(msg)
            continue
            
        text_content = msg["content"]
        matches = VISION_REGEX.findall(text_content)
        
        if not matches:
            hydrated.append(msg)
            continue
            
        # Se for mensagem antiga, substitui a tag por um aviso leve em texto
        if i < recent_threshold:
            clean_text = VISION_REGEX.sub("[Imagem enviada anteriormente neste ponto da conversa. A.I. já analisou o contexto.]", text_content).strip()
            hydrated.append({
                "role": msg["role"],
                "content": clean_text
            })
            continue

        has_vision = True
        clean_text = VISION_REGEX.sub("", text_content).strip()
        
        content_array = []
        if clean_text:
            content_array.append({"type": "text", "text": clean_text})
        else:
            content_array.append({"type": "text", "text": "Por favor analise a imagem anexada."})
            
        for path in matches:
            try:
                if os.path.exists(path):
                    with open(path, "rb") as bf:
                        img_b64 = base64.b64encode(bf.read()).decode("utf-8")
                    mime_type, _ = mimetypes.guess_type(path)
                    if not mime_type:
                        mime_type = "image/jpeg"
                    
                    content_array.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{img_b64}"
                        }
                    })
                else:
                    logger.warning(f"File not found for vision payload: {path}")
            except Exception as e:
                logger.error(f"Error hydrating vision payload for {path}: {e}")
                
        # Só substitui se hidratou imagens com sucesso
        if len(content_array) > 1 or (len(content_array) == 1 and content_array[0]["type"] == "image_url"):
            hydrated.append({
                "role": msg["role"],
                "content": content_array
            })
        else:
            hydrated.append(msg)
            
    return hydrated, has_vision


async def classify_intent(text: str, router: LLMRouter) -> tuple[str, str | None]:
    """
    Classifica intent em 2 etapas:
    1. Keywords rápidas (sem chamar LLM)
    2. Se não bateu keyword, pede pro LLM classificar
    """
    text_lower = text.lower().strip()

    # URLs na mensagem → auto-read
    urls = URL_REGEX.findall(text)
    if urls:
        return ("url_read", urls[0])

    # Memory save
    for kw in MEMORY_SAVE_KEYWORDS:
        if kw in text_lower:
            fact = text_lower
            for k in MEMORY_SAVE_KEYWORDS:
                fact = fact.replace(k, "").strip()
            return ("save_memory", fact or text)

    # Memory recall
    for kw in MEMORY_RECALL_KEYWORDS:
        if kw in text_lower:
            return ("recall_memory", None)

    # Deep Research
    for kw in DEEP_RESEARCH_KEYWORDS:
        if kw in text_lower:
            query = text_lower
            for k in DEEP_RESEARCH_KEYWORDS:
                query = query.replace(k, "").strip()
            return ("deep_research", query or text)

    # Swarm Orchestrator (Personas Estáticas)
    for kw in SWARM_KEYWORDS:
        if kw in text_lower:
            query = text_lower
            for k in SWARM_KEYWORDS:
                query = query.replace(k, "").strip()
            return ("swarm", query or text)

    # Reminders
    for kw in REMINDER_KEYWORDS:
        if kw in text_lower:
            return ("reminder", text)

    # Weather
    for kw in WEATHER_KEYWORDS:
        if kw in text_lower:
            return ("weather", None)

    # System status
    for kw in STATUS_KEYWORDS:
        if kw in text_lower:
            return ("status", None)

    # Cyber-Mãos (Hardware control)
    for kw in CYBER_HANDS_KEYWORDS:
        if kw in text_lower:
            if any(w in text_lower for w in ["lanterna", "luz", "ilumina"]):
                is_on = not any(w in text_lower for w in ["apagar", "desligar", "off"])
                return ("flashlight", "on" if is_on else "off")
            elif any(w in text_lower for w in ["onde", "localização", "localizacao", "gps", "coordenadas"]):
                return ("location", None)

    # Council
    for kw in COUNCIL_KEYWORDS:
        if kw in text_lower:
            query = text_lower
            for k in COUNCIL_KEYWORDS:
                query = query.replace(k, "").strip()
            return (INTENT_COUNCIL, query or text)

    # Sandbox (E2B Cloud Code Interpreter)
    for kw in SANDBOX_KEYWORDS:
        if kw in text_lower:
            query = text_lower
            for k in SANDBOX_KEYWORDS:
                query = query.replace(k, "").strip()
            return ("sandbox", query or text)

    # Search
    for kw in SEARCH_KEYWORDS:
        if kw in text_lower:
            query = text_lower
            for k in SEARCH_KEYWORDS:
                query = query.replace(k, "").strip()
            return ("search", query or text)

    # LLM classifica (rápido)
    try:
        classification = await router.generate([
            {"role": "system", "content": (
                "Classifique a intenção APENAS como SEARCH ou CHAT. "
                "SEARCH = precisa de informação atualizada da internet. "
                "CHAT = conversa normal, opinião, saudação. "
                "Responda só a palavra."
            )},
            {"role": "user", "content": text},
        ], temperature=0.0, require_fast=True)

        if isinstance(classification, str) and "SEARCH" in classification.upper():
            logger.info(f"🤖 LLM classificou como SEARCH: {text[:50]}")
            return ("search", text)
    except Exception as e:
        logger.warning(f"⚠️ Classificação falhou: {e}")

    return ("chat", None)


async def classify_intent_with_tools(text: str, router: LLMRouter) -> tuple[str, str | None]:
    """
    Tenta classificar o intent usando OpenAI Function Calling.
    Se o provider falhar ou devolver texto comum, levanta exceção para acionar fallback.
    """
    messages = [
        {"role": "system", "content": "Você é o núcleo de classificação de comandos da IARA. Seu trabalho é ler a intenção do usuário e invocar a ferramenta mais adequada. Se for papo furado ou nenhuma tool se encaixar perfeitamente, não chame tools, apenas retorne texto vazio."},
        {"role": "user", "content": text}
    ]
    active_tools = list(tools_registry.TOOLS_REGISTRY)
    
    # Heurística Rápida (Lazy Loading) para evitar Token Bloat
    mcp_keywords = r"\b(acessa|abre|navega|arquivo|repositório|executa|pesquisa|leia|baixa|github|mcp)\b"
    if re.search(mcp_keywords, text, re.IGNORECASE):
        logger.info("Detectada intenção de uso externo. Carregando ferramentas MCP disponíveis...")
        mcp_tools = await mcp_client.list_tools()
        for mt in mcp_tools:
            # Assinatura unificada: mcp__{server_name}__{tool_name}
            safe_server_name = str(mt.get("mcp_server", "unknown")).replace("-", "_")
            safe_tool_name = str(mt.get("name", "tool")).replace("-", "_")
            tool_id = f"mcp__{safe_server_name}__{safe_tool_name}"
            
            active_tools.append({
                "type": "function",
                "function": {
                    "name": tool_id,
                    "description": mt.get("description", f"Ferramenta externa do servidor {safe_server_name}"),
                    "parameters": mt.get("inputSchema", {"type": "object", "properties": {}})
                }
            })

    response = await router.generate(
        messages=messages,
        tools=active_tools,
        task_type="tools",
        require_fast=True  # Preferência Groq
    )
    
    if isinstance(response, dict) and "tool" in response:
        tool = response["tool"]
        args = response.get("args", {})
        
        # Mapeamento Crítico Tool → Intent legado
        if tool == "web_search":
            return ("search", args.get("query"))
        elif tool == "deep_research":
            return ("deep_research", args.get("query"))
        elif tool == "save_memory":
            return ("save_memory", args.get("content"))
        elif tool == "recall_memory":
            return ("recall_memory", None)
        elif tool == "get_weather":
            return ("weather", None)
        elif tool == "get_system_status":
            return ("status", None)
        elif tool == "set_reminder":
            msg = args.get("message", "")
            time_expr = args.get("time_expression", "")
            return ("reminder", f"{msg} {time_expr}".strip())
        elif tool == "toggle_flashlight":
            return ("flashlight", args.get("state"))
        elif tool == "get_location":
            return ("location", None)
        elif tool == "read_url":
            return ("url_read", args.get("url"))
        elif tool == "run_sandbox":
            return ("sandbox", args.get("task_description"))
        elif tool == "swarm_delegate":
            return ("swarm", args.get("task"))
        elif tool == "deep_research_council":
            return ("council", args.get("query"))
        elif tool.startswith("mcp__"):
            parts = tool.split("__", 2)
            if len(parts) == 3:
                return ("mcp", {"server_name": parts[1], "tool_name": parts[2], "args": args})
            
    # Se não retornou dicionário de tool válida, acionamos um TypeError para o fallback entrar em ação
    raise ValueError("Nenhuma tool explícita foi invocada pelo LLM.")


def parse_reminder_time(text: str) -> tuple[str, datetime | None]:
    """
    Extrai duração/horário do texto do reminder.
    Retorna (mensagem_limpa, horário_trigger).
    """
    now = datetime.now()

    # "daqui a X minutos/horas"
    match = re.search(r'daqui\s+(?:a\s+)?(\d+)\s*(min(?:uto)?s?|hora?s?|seg(?:undo)?s?)', text, re.IGNORECASE)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        if 'hora' in unit or unit.startswith('h'):
            delta = timedelta(hours=amount)
        elif 'seg' in unit:
            delta = timedelta(seconds=amount)
        else:
            delta = timedelta(minutes=amount)

        # Limpar o texto
        msg = re.sub(r'daqui\s+(?:a\s+)?\d+\s*\S+', '', text, flags=re.IGNORECASE).strip()
        # Remover keywords do reminder
        for kw in REMINDER_KEYWORDS:
            msg = msg.replace(kw, "").strip()
        return (msg or text, now + delta)

    # "às HH:MM" ou "as HH:MM"
    match = re.search(r'[àa]s?\s+(\d{1,2})[h:](\d{2})?', text, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        target = now.replace(hour=hour, minute=minute, second=0)
        if target < now:
            target = target + timedelta(days=1)

        msg = re.sub(r'[àa]s?\s+\d{1,2}[h:]\d{0,2}', '', text, flags=re.IGNORECASE).strip()
        for kw in REMINDER_KEYWORDS:
            msg = msg.replace(kw, "").strip()
        return (msg or text, target)

    # Não conseguiu parsear → retorna None
    msg = text
    for kw in REMINDER_KEYWORDS:
        msg = msg.replace(kw, "").strip()
    return (msg or text, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Brain — Lógica principal
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

router = LLMRouter()
_reminder_chat_id = None  # Salva o chat_id pra enviar lembretes
_cot_enabled = False  # Chain of Thought toggle
_reflect_enabled = False  # Auto-reflexão toggle


async def build_system_prompt(query_embedding: list[float] | None = None, project_id: int | None = None) -> str:
    """Monta o system prompt estruturado em 4 Camadas de Memória Semântica Avançada."""
    identity = core.load_identity()
    
    # Busca dados no banco para as 4 camadas (RAG via Similaridade de Cosseno se query_embedding estiver presente)
    facts = await core.get_semantic_core_facts(query_embedding, limit=5, project_id=project_id)
    episodes = await core.get_semantic_episodes(query_embedding, limit=3, project_id=project_id)
    reflections = await core.get_active_reflections()
    working_count = await core.get_working_memory_count()

    # Camada 1: Metadata & Estatísticas (Sintético por enquanto)
    # TODO: Implementar query real de uso no futuro
    layer1_meta = (
        f"⏳ Interações na sessão ativa: {working_count}/10 antes da compactação.\n"
        f"🧠 Confiança média nas regras deduzidas: Alta (Confidence Score ativo)."
    )

    # Camada 2: Preferências do Assistente (Regras de ouro e Fatos Core)
    lines_pref = []
    lines_facts = []
    if facts:
        for f in facts:
            score = f.get('confidence', 1.0)
            if "preferencia" in f['category'].lower() or "regra" in f['category'].lower():
                lines_pref.append(f"- [Confidence: {score:.2f}] {f['content']}")
            else:
                lines_facts.append(f"- {f['content']}")
    
    layer2_prefs = "\n".join(lines_pref) if lines_pref else "- Nenhuma regra de ouro estrita detectada."
    if lines_facts:
        layer2_prefs += "\n\n💡 Fatos Permanentes:\n" + "\n".join(lines_facts)

    if reflections:
        layer2_prefs += "\n\n💡 Auto-Reflexões (Lições Aprendidas):\n" + "\n".join(f"- {r}" for r in reflections)

    # Camada 3: Tópicos Ativos (Histórico Alto-Nível)
    layer3_topics = ""
    if episodes:
        layer3_topics = "\n".join(f"- {ep['summary']}" for ep in episodes)
    else:
        layer3_topics = "- Nenhum tópico denso recente."

    # Camada 4: Retomada Densa (Contexto conversacional puro — injetado pela própria LLMRouter como messages)
    
    # Contexto temporal
    now = datetime.now()
    time_ctx = now.strftime("Hoje é %A, %d/%m/%Y. São %H:%M (horário de Brasília).")
    days_pt = {
        "Monday": "segunda-feira", "Tuesday": "terça-feira",
        "Wednesday": "quarta-feira", "Thursday": "quinta-feira",
        "Friday": "sexta-feira", "Saturday": "sábado", "Sunday": "domingo",
    }
    for en, pt in days_pt.items():
        time_ctx = time_ctx.replace(en, pt)

    return f"""{identity}

{time_ctx}

=========================================
INJEÇÃO DE MEMÓRIA (4 CAMADAS SEMÂNTICAS)
=========================================

[CAMADA 1: METADADOS DE INTERAÇÃO]
{layer1_meta}

[CAMADA 2: PREFERÊNCIAS E REGRAS DE OURO]
{layer2_prefs}

[CAMADA 3: TÓPICOS ATIVOS RECENTES]
{layer3_topics}

[CAMADA 4: RETOMADA DENSA]
(Verifique as mensagens mais recentes abaixo neste histórico de chat).
=========================================
"""


async def execute_tools(text: str) -> tuple[str, str, str | None]:
    """Classifica a intenção e executa a tool correspondente, retornando o contexto. Retorna (tool_context, intent, query)."""
    
    try:
        # Tenta Function Calling primeiro
        intent, query = await classify_intent_with_tools(text, router)
        logger.info(f"🎯 Intent (Tool Use): {intent} | Query: {query}")
    except Exception as e:
        # Fallback silencioso pro regex legado (Cerebras ou falhas)
        logger.debug(f"⚠️ Tool Use falhou ({e}), acionando Fallback Keywords...")
        intent, query = await classify_intent(text, router)
        logger.info(f"🎯 Intent (Keywords): {intent} | Query: {query}")

    tool_context = ""

    if intent == "search" and query:
        logger.info(f"🔍 Buscando (deep): {query}")
        search_results = await web_search.web_search_deep(query)
        tool_context = f"\n\n## Resultados da busca web (use esses dados para responder com precisão):\n{search_results}"

    elif intent == "save_memory" and query:
        await core.save_core_fact("fato", query)
        logger.info(f"💾 Memória salva: {query}")
        tool_context = f"\n\n## [AÇÃO EXECUTADA] Fato salvo na memória permanente: '{query}'. Confirme brevemente."

    elif intent == "recall_memory":
        core_facts = await core.get_core_memory()
        if core_facts:
            facts_text = "\n".join([f"- [{f['category']}] {f['content']}" for f in core_facts])
            tool_context = f"\n\n## Tudo que sei sobre o Criador:\n{facts_text}"
        else:
            tool_context = "\n\n## Ainda não tenho fatos permanentes salvos."

    elif intent == "weather":
        weather_data = await core.get_weather()
        logger.info("🌤️ Clima consultado")
        tool_context = f"\n\n## Dados do clima (Open-Meteo):\n{weather_data}"

    elif intent == "status":
        status_data = await core.get_system_status()
        logger.info("📱 Status do sistema consultado")
        tool_context = f"\n\n## Status do dispositivo:\n{status_data}"

    elif intent == "flashlight":
        is_on = query == "on"
        result = await core.turn_on_flashlight(on=is_on)
        logger.info(f"🔦 Controle de lanterna executado: {result}")
        tool_context = f"\n\n## [AÇÃO FÍSICA EXECUTADA]\n{result}"

    elif intent == "location":
        result = await core.get_location()
        logger.info(f"📍 GPS consultado: {result}")
        tool_context = f"\n\n## [AÇÃO FÍSICA EXECUTADA]\nSensoriamento de localização concluído:\n{result}"

    elif intent == "url_read" and query:
        logger.info(f"🔗 Lendo URL: {query}")
        content = await web_search.web_read(query)
        tool_context = f"\n\n## Conteúdo da URL {query}:\n{content}"

    elif intent == "reminder" and query:
        msg, trigger = parse_reminder_time(query)
        if trigger:
            rid = await core.save_reminder(msg, trigger)
            time_str = trigger.strftime("%H:%M")
            logger.info(f"⏰ Reminder #{rid} agendado para {time_str}: {msg}")
            tool_context = f"\n\n## [AÇÃO EXECUTADA] Lembrete agendado para {time_str}: '{msg}'. Confirme brevemente."
        else:
            tool_context = "\n\n## Não entendi o horário do lembrete. Peça ao Criador pra esclarecer (ex: 'daqui a 10 minutos' ou 'às 18:00')."
            
    elif intent == "swarm" and query:
        logger.info(f"🐝 Enviando task para o Swarm Orchestrator: {query[:50]}")
        
        # Determinar a role dinamicamente (Mock rápido, ideal usar LLM pra classificar a melhor role)
        # Vamos assumir que se tem "revisa" ou "código", é revisor. Senão, pesquisador.
        role_to_use = "revisor" if any(w in query.lower() for w in ["revisa", "código", "codigo", "bug"]) else "pesquisador"
        
        # Função de callback pra quando o swarm terminar
        async def swarm_callback(result_text):
            if _reminder_chat_id:
                final_msg = f"🐝 **Retorno do Swarm ({role_to_use}):**\n\n{result_text}"
                await telegram_bot.send_simple_message(_reminder_chat_id, final_msg[:4000])
                
        # Submete à fila do orquestrador (não bloqueia a Iara)
        await orchestrator.submit_task(role_to_use, query, callback=swarm_callback)
        
        tool_context = f"\n\n## [AÇÃO EXECUTADA] A tarefa '{query}' foi delegada para a fila do Swarm com a persona '{role_to_use}'. Diga ao criador que a equipe está trabalhando nisso em background e avisará quando terminar."

    elif intent == "sandbox" and query:
        logger.info(f"☁️ Gerando código Python para a Sandbox E2B: {query}")
        
        # Early-exit check to save tokens if API Key is missing
        if not os.getenv("E2B_API_KEY"):
            return "\n\n## [ERRO CRÍTICO] A chave E2B_API_KEY não está configurada no .env. Impossível ligar os motores da Sandbox Cloud.", intent, query

        # Pede pra LLM gerar o código python puro
        code_prompt = f"Escreva APENAS código Python para a seguinte solicitação: {query}. O código deve ser self-contained e printar o resultado ou plotar gráficos se necessário. Não use blocos markdown (```python), apenas o código puro."
        generated_code = await router.generate([{"role": "user", "content": code_prompt}], task_type="code", require_fast=True)
        
        # Limpa markers de markdown caso a LLM insista em enviar
        if isinstance(generated_code, str):
            generated_code = generated_code.replace("```python", "").replace("```", "").strip()
            
        if generated_code:
            # Carrega e aciona a Skill Oficial Declarativa
            from skills.e2b_sandbox_skill import execute as e2b_execute
            sandbox_result = await e2b_execute({"code": generated_code})
            
            tool_context = f"\n\n## [AÇÃO EXECUTADA] O código foi gerado e executado na Nuvem E2B.\n\nCódigo Python Executado:\n```python\n{generated_code}\n```\n\nOutput da Máquina Virtual:\n{sandbox_result}\n\nVocê deve encaminhar esse Output da Máquina Virtual (incluindo imagens base64 se houverem) em sua resposta."
        else:
            tool_context = f"\n\n## [ERRO] O CodeAgent falhou em escrever o código Python: {generated_code}"

    elif intent == "mcp" and isinstance(query, dict):
        server_name = query.get("server_name")
        tool_name = query.get("tool_name")
        mcp_args = query.get("args", {})
        
        logger.info(f"🔌 Acionando MCP Tool: {server_name}.{tool_name}")
        # Notificar na interface que estamos acionando a ferramenta ex: [MCP] github.read_file
        
        # Chama a tool com o timeout nativo do client
        result = await mcp_client.call_tool(server_name, tool_name, mcp_args)
        tool_context = f"\n\n## Resultado da Ferramenta MCP ({server_name}.{tool_name}):\n{result}"

    return tool_context, intent, query

async def process_message(text: str, message):
    """
    Pipeline principal:
    1. Comandos especiais → 2. Salva mensagem → 3. Classifica intent
    4. Executa tool → 5. Chama LLM → 6. Auto-detect → 7. Compacta
    """
    global _reminder_chat_id, _cot_enabled, _reflect_enabled
    chat_id = message.chat.id
    _reminder_chat_id = chat_id

    # Recupera o projeto ativo
    active_project_id_str = await core.get_app_config("active_project_id")
    project_id = int(active_project_id_str) if active_project_id_str and active_project_id_str.isdigit() else None

    # Embeddar a query do usuário assincronamente (Semantic RAG)
    query_embedding = await embeddings.generate_query_embedding(text)

    # 0. Comandos especiais (não salvam na memória)
    text_lower = text.strip().lower()
    if text_lower in ("/think on", "/think", "think on"):
        _cot_enabled = True
        await telegram_bot.send_simple_message(chat_id, "🧠 **Chain of Thought ativado.** Vou mostrar meu raciocínio antes de responder.")
        return
    elif text_lower in ("/think off", "think off"):
        _cot_enabled = False
        await telegram_bot.send_simple_message(chat_id, "💬 **Chain of Thought desativado.** Respostas diretas.")
        return
    elif text_lower in ("/reflect on", "/reflect", "reflect on"):
        _reflect_enabled = True
        await telegram_bot.send_simple_message(chat_id, "🔍 **Auto-reflexão ativada.** Vou avaliar minhas respostas silenciosamente.")
        return
    elif text_lower in ("/reflect off", "reflect off"):
        _reflect_enabled = False
        await telegram_bot.send_simple_message(chat_id, "🔍 **Auto-reflexão desativada.**")
        return

    # Comandos /worker
    elif text_lower.startswith("/worker"):
        parts = text.strip().split()
        if len(parts) >= 4 and parts[1].lower() == "add":
            name = parts[2]
            host = parts[3]
            skills = parts[4].split(",") if len(parts) > 4 else None
            worker_protocol.register_worker(name, host, skills)
            await telegram_bot.send_simple_message(chat_id, f"🐝 Worker **{name}** registrado ({host})")
        elif len(parts) >= 3 and parts[1].lower() == "remove":
            name = parts[2]
            worker_protocol.remove_worker(name)
            await telegram_bot.send_simple_message(chat_id, f"🐝 Worker **{name}** removido.")
        elif len(parts) >= 2 and parts[1].lower() in ("list", "ls", "status"):
            status = worker_protocol.list_all_workers()
            await telegram_bot.send_simple_message(chat_id, status)
        elif len(parts) >= 2 and parts[1].lower() == "ping":
            await telegram_bot.send_simple_message(chat_id, "🐝 Verificando workers...")
            await worker_protocol.health_check()
            status = worker_protocol.list_all_workers()
            await telegram_bot.send_simple_message(chat_id, status)
        else:
            await telegram_bot.send_simple_message(chat_id, (
                "🐝 **Comandos Worker:**\n"
                "`/worker add nome host [skills]`\n"
                "`/worker remove nome`\n"
                "`/worker list`\n"
                "`/worker ping`"
            ))
        return

    # Comandos de Isolamento de Projeto (Phase 12)
    elif text_lower.startswith("/projeto"):
        parts = text.strip().split(maxsplit=1)
        if len(parts) > 1:
            proj_name = parts[1].strip()
            # Se chamou "none" ou "global", desativa
            if proj_name.lower() in ("none", "global", "clear", "null"):
                await core.set_app_config("active_project_id", "")
                await telegram_bot.send_simple_message(chat_id, "🌍 **Escopo Global** ativado (Sem projeto).")
            else:
                new_proj_id = await core.get_or_create_project(proj_name)
                await core.set_app_config("active_project_id", str(new_proj_id))
                await telegram_bot.send_simple_message(chat_id, f"✅ Projeto ativo alterado para: **{proj_name}**")
        else:
            # Apenas mostra o ativo
            if project_id:
                p_name = await core.get_project_name(project_id)
                await telegram_bot.send_simple_message(chat_id, f"🏢 Projeto ativo atual: **{p_name or 'Desconhecido'}**\nUse `/projeto [nome]` para trocar.")
            else:
                await telegram_bot.send_simple_message(chat_id, "🌍 Nenhum projeto ativo (Escopo Global).\nUse `/projeto [nome]` para criar/entrar em um.")
        return

    # Comandos Manual / Task Management (Stateful Todo)
    elif text_lower.startswith("/task"):
        parts = text.strip().split(" ", 2)
        cmd = parts[1].lower() if len(parts) > 1 else "list"
        
        if cmd == "add" and len(parts) > 2:
            desc = parts[2]
            tid = await core.add_task_state(desc)
            await telegram_bot.send_simple_message(chat_id, f"📝 **Tarefa #{tid} pendente:** {desc}")
        elif cmd == "start" and len(parts) > 2:
            tid = parts[2]
            # Verifica se já tem in_progress
            active = await core.get_active_task()
            if active and str(active["id"]) != tid:
                await telegram_bot.send_simple_message(chat_id, f"⚠️ Trava de Fluxo: A tarefa #{active['id']} já está em progresso. Conclua-a primeiro (/task done {active['id']}).")
                return
            await core.set_task_status(int(tid), "in_progress")
            await telegram_bot.send_simple_message(chat_id, f"🚀 **Iniciando tarefa #{tid}**.")
        elif cmd == "done" and len(parts) > 2:
            tid = parts[2]
            await core.set_task_status(int(tid), "completed")
            await telegram_bot.send_simple_message(chat_id, f"✅ **Tarefa #{tid} concluída!**")
        else:
            active = await core.get_active_task()
            msg = "📋 **Status das Tarefas:**\n"
            msg += f"Em progresso: #{active['id']} - {active['description']}\n" if active else "Em progresso: Nenhuma\n"
            msg += "\nComandos: `/task add [desc]`, `/task start [id]`, `/task done [id]`"
            await telegram_bot.send_simple_message(chat_id, msg)
        return

    # Tools Catalog
    elif text_lower == "/tools":
        msg = "🛠️ **Catálogo de Ferramentas Ativas (Function Calling):**\n\n"
        for t in tools_registry.TOOLS_REGISTRY:
            f = t["function"]
            msg += f"- **{f['name']}**: {f['description']}\n"
        await telegram_bot.send_simple_message(chat_id, msg)
        return

    # Comandos de Scheduler (Phase 14)
    elif text_lower.startswith("/cron"):
        parts = text.strip().split(maxsplit=4)
        cmd = parts[1].lower() if len(parts) > 1 else "list"
        
        if cmd == "list":
            jobs = await core.get_all_scheduled_jobs()
            if not jobs:
                await telegram_bot.send_simple_message(chat_id, "Nenhum job agendado.")
            else:
                msg = "📅 **Jobs Autônomos (Background Scheduler):**\n\n"
                for j in jobs:
                    status = "🟢 ON" if j["enabled"] else "🔴 OFF"
                    msg += f"**{j['name']}** ({status})\n- Cron: `{j['cron']}`\n- Action: `{j['action']}`\n- Last: {j['last_run']}\n\n"
                await telegram_bot.send_simple_message(chat_id, msg)
        elif cmd == "add" and len(parts) == 5:
            # parts = ['/cron', 'add', 'nome', 'cron', 'acao param1...']
            action_params = parts[4].split(maxsplit=1)
            action = action_params[0]
            params = {}
            if len(action_params) > 1:
                import json
                try:
                    params = json.loads(action_params[1])
                except:
                    pass
            await core.add_scheduled_job(parts[2], parts[3], action, params)
            await telegram_bot.send_simple_message(chat_id, f"✅ Job '{parts[2]}' cadastrado com sucesso.")
        elif cmd == "toggle" and len(parts) >= 3:
            name = parts[2]
            try:
                new_state = await core.toggle_job(name)
                status = "🟢 ATIVADO" if new_state else "🔴 DESATIVADO"
                await telegram_bot.send_simple_message(chat_id, f"✅ Job '{name}' foi {status}.")
            except ValueError as e:
                await telegram_bot.send_simple_message(chat_id, f"⚠️ Erro: {e}")
        elif cmd == "remove" and len(parts) >= 3:
            name = parts[2]
            removed = await core.delete_scheduled_job(name)
            if removed:
                await telegram_bot.send_simple_message(chat_id, f"🗑️ Job '{name}' removido.")
            else:
                await telegram_bot.send_simple_message(chat_id, f"⚠️ Job '{name}' não existe.")
        elif cmd == "run" and len(parts) >= 3:
            name = parts[2]
            jobs = await core.get_all_scheduled_jobs()
            job = next((j for j in jobs if j["name"] == name), None)
            if job:
                await telegram_bot.send_simple_message(chat_id, f"⚡ Forçando execução de '{name}'...")
                asyncio.create_task(scheduler.execute_action(job, send_proactive_message))
                await core.update_job_last_run(job["id"])
            else:
                await telegram_bot.send_simple_message(chat_id, f"⚠️ Job '{name}' não encontrado.")
        else:
            await telegram_bot.send_simple_message(chat_id, (
                "📅 **Comandos do Scheduler:**\n"
                "`/cron list`\n"
                "`/cron add [nome] [cron] [acao] [params_json]`\n"
                "`/cron toggle [nome]`\n"
                "`/cron remove [nome]`\n"
                "`/cron run [nome]`"
            ))
        return

    # Comandos MCP (Model Context Protocol)
    elif text_lower.startswith("/mcp"):
        parts = text.strip().split()
        cmd = parts[1].lower() if len(parts) > 1 else "status"
        
        if cmd == "status":
            report = await mcp_client.get_status_report()
            await telegram_bot.send_simple_message(chat_id, report)
            
        elif cmd == "add" and len(parts) >= 4:
            # /mcp add nome url [token]
            name = parts[2]
            url = parts[3]
            token = parts[4] if len(parts) > 4 else None
            success = await mcp_client.register_server(name, url, token)
            if success:
                await telegram_bot.send_simple_message(chat_id, f"✅ Servidor MCP '{name}' registrado com sucesso.\nUse `/mcp status` para testar a conexão.")
            else:
                await telegram_bot.send_simple_message(chat_id, f"❌ Erro ao registrar o servidor MCP '{name}'.")
                
        elif cmd == "remove" and len(parts) >= 3:
            name = parts[2]
            success = await mcp_client.remove_server(name)
            if success:
                await telegram_bot.send_simple_message(chat_id, f"🗑️ Servidor MCP '{name}' removido.")
            else:
                await telegram_bot.send_simple_message(chat_id, f"❌ Erro ao remover o servidor MCP '{name}'.")
                
        elif cmd == "list":
            servers = await mcp_client.get_all_servers()
            if not servers:
                await telegram_bot.send_simple_message(chat_id, "Nenhum servidor vinculado.")
            else:
                msg = "📋 **Servidores MCP Configurados:**\n\n"
                for s in servers:
                    msg += f"- **{s['name']}** `{s['url']}`\n"
                await telegram_bot.send_simple_message(chat_id, msg)
        else:
            await telegram_bot.send_simple_message(chat_id, (
                "🔌 **Comandos MCP:**\n"
                "`/mcp status` - Testa e lista conexões com os tools\n"
                "`/mcp list` - Apenas lista os endpoints no banco\n"
                "`/mcp add [nome] [url] [token_opcional]`\n"
                "`/mcp remove [nome]`"
            ))
        return

    # Plan Mode Lock
    elif text_lower in ("/plan on", "/planmode on"):
        await telegram_bot.send_channel_message(chat_id, "🔒 **EnterPlanMode**: Agente bloqueado para edição. Apenas pesquisas e arquitetura permitidas.", channel="commentary")
        await core.save_message("system", "O usuário ativou o PlanMode. Edição de código está bloqueada. Gere um plano e peça aprovação via ExitPlanMode.")
        return
    elif text_lower in ("/plan off", "/planmode off"):
        await telegram_bot.send_channel_message(chat_id, "🔓 **ExitPlanMode**: Plano aprovado. Edição de código liberada.", channel="commentary")
        await core.save_message("system", "O usuário desativou o PlanMode (ExitPlanMode). Você está autorizado a implementar o código.")
        return

    # Comando Manual pra testar consolidação
    elif text_lower == "/consolidate":
        await telegram_bot.send_simple_message(chat_id, "🧠 Iniciando consolidação de memória manual...")
        asyncio.create_task(core.consolidate_working_memory())
        return

    # 0.5 Interceptar documentos anexados
    if text.startswith("📄FILE:"):
        parts = text[len("📄FILE:"):].split("|", 1)
        file_path = parts[0]
        question = parts[1] if len(parts) > 1 else None
        logger.info(f"📄 Analisando documento: {file_path}")
        await telegram_bot.send_channel_message(chat_id, "📄 Analisando documento...", channel="commentary")
        result = await doc_reader.analyze_document(file_path, router, question)
        await telegram_bot.send_channel_message(chat_id, result, channel="final")
        await core.save_message("assistant", result)
        return

    # 1. Salvar mensagem do Criador
    await core.save_message("user", text, project_id=project_id)

    # 1.5 Verificar se há plano de pesquisa pendente de aprovação
    pending = deep_research.get_pending_plan(chat_id)
    if pending:
        approval_words = ["ok", "sim", "vai", "pode", "aprova", "aprovar", "manda", "go", "yes", "bora", "faz", "inicia", "iniciar"]
        if any(w == text_lower or text_lower.startswith(w) for w in approval_words):
            # Aprovado! Executar plano
            deep_research.clear_pending_plan(chat_id)
            topic = pending["topic"]
            plan = pending["plan"]

            await telegram_bot.send_simple_message(chat_id, "🔬 **Pesquisa iniciada!** Acompanhe o progresso abaixo...")

            # Callback de progresso — envia updates pro Telegram
            async def progress_cb(msg: str):
                await telegram_bot.send_simple_message(chat_id, msg)

            # Executar plano com progresso
            all_data, sources = await deep_research.execute_plan(topic, plan, router, progress_cb)
            tipo = plan.get("tipo", "EXPLORATÓRIA") if isinstance(plan, dict) else "EXPLORATÓRIA"
            await progress_cb(f"📝 Sintetizando relatório...\nTipo: {tipo} | Fontes: {len(sources)}")
            report = await deep_research.synthesize_with_citations(topic, all_data, sources, router, tipo=tipo)

            await telegram_bot.send_simple_message(chat_id, report)
            await core.save_message("assistant", report, project_id=project_id)
            return
        else:
            # Usuário editou o plano — cancelar e tratar como mensagem normal
            deep_research.clear_pending_plan(chat_id)
            logger.info("📋 Plano de pesquisa cancelado/editado pelo Criador")

    # 2. Classificar intent e Executar tool se necessário
    tool_context, intent, query = await execute_tools(text)

    if intent == "deep_research" and query:
        logger.info(f"🔬 Deep Research Plan & Execute: {query}")
        await telegram_bot.send_channel_message(chat_id, "🔬 Analisando tema e criando plano de pesquisa...", channel="commentary")
        
        # Fase 1: Criar plano
        plan = await deep_research.create_plan(query, router)
        plan_msg = deep_research.format_plan_message(query, plan)
        
        # Fase 2: Mostrar plano e aguardar aprovação
        deep_research.save_pending_plan(chat_id, query, plan)
        await telegram_bot.send_channel_message(chat_id, plan_msg, channel="final")
        await core.save_message("assistant", plan_msg, project_id=project_id)
        return  # Aguarda resposta do usuário

    if intent == INTENT_COUNCIL:
        logger.info(f"⚖️ Iniciando Conselho Expandido para: {query}")
        await telegram_bot.send_channel_message(chat_id, "⚖️ Convocando Conselho Multi-Modal (Groq, Cerebras, Mistral)...", channel="commentary")
        
        system_prompt = await build_system_prompt(query_embedding, project_id)
        conversation = await core.get_conversation(project_id=project_id)
        base_messages = [
            {"role": "system", "content": system_prompt + tool_context},
            *conversation,
            {"role": "user", "content": query},
        ]
        
        # Função para buscar opinião de um provedor
        async def fetch_council(provider_name):
            try:
                result = await router.generate(base_messages, task_type="chat", require_fast=True, force_provider=provider_name)
                return f"### Opinião [{provider_name.upper()}]:\n{result}"
            except Exception as e:
                return f"### Opinião [{provider_name.upper()}] falhou:\n{e}"
                
        # Substitui kimi se quisermos fast gen com openweights
        providers = ["groq", "cerebras", "mistral"] 
        tasks = [fetch_council(p) for p in providers]
        
        responses = await asyncio.gather(*tasks)
        council_output = "\n\n".join(responses)
        
        await telegram_bot.send_channel_message(chat_id, "🏛️ Conselho finalizado. Sintetizando veredicto Presidencial (OpenRouter/R1 ou Groq)...", channel="commentary")
        
        president_messages = [
            {"role": "system", "content": system_prompt + "\nVocê é a Consciência Presidencial (Líder do Conselho de I.A). O Criador fez uma pergunta complexa e acionou a Reunião Distribuída. Leia as opiniões conflitantes/divergentes abaixo dos seus conselheiros e crie UM ÚNICO veredicto ou resposta final unificada. Aponte e cite as melhores ideias de cada conselheiro se forem válidas."},
            {"role": "user", "content": f"Pergunta original do Criador: {query}\n\n{council_output}"}
        ]
        
        stream = router.generate_stream(president_messages, task_type="reasoning", require_fast=False)
        full_response = await telegram_bot.send_streaming_response(
            chat_id, stream, reply_to=message.message_id if message else None
        )
        if full_response:
            await core.save_message("assistant", full_response, project_id=project_id)
        return

    # 4. Montar contexto e streaming
    system_prompt = await build_system_prompt(query_embedding, project_id)

    # Injetar CoT se ativado
    cot_instruction = ""
    if _cot_enabled:
        cot_instruction = (
            "\n\n## Modo Chain of Thought ATIVADO\n"
            "Antes de responder, raciocine passo-a-passo dentro de tags <think>...</think>.\n"
            "Depois da tag </think>, dê a resposta final normalmente.\n"
            "Exemplo:\n"
            "<think>O Criador perguntou X. Preciso considerar Y e Z...</think>\n"
            "Resposta final aqui."
        )

    conversation = await core.get_conversation(project_id=project_id)
    messages = [
        {"role": "system", "content": system_prompt + tool_context + cot_instruction},
        *conversation,
    ]

    # Fase 8: Definição Semântica e Escalation Trigger
    task_type_call = "chat"
    req_fast = True
    
    if any(w in text_lower for w in REASONING_KEYWORDS):
        task_type_call = "reasoning"
        req_fast = False
        await telegram_bot.send_channel_message(chat_id, "🧠 Escalando para DeepSeek R1 (OpenRouter) por complexidade semântica detectada...", channel="commentary")

    stream = router.generate_stream(messages, task_type=task_type_call, require_fast=req_fast)
    full_response = await telegram_bot.send_streaming_response(
        chat_id, stream, reply_to=message.message_id
    )

    # 5. Processar CoT — extrair e enviar raciocínio separado (Analysis Channel)
    if full_response and _cot_enabled:
        think_match = re.search(r'<think>(.*?)</think>', full_response, re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()
            # Enviar o raciocínio como mensagem no canal invisível
            if thinking:
                await telegram_bot.send_channel_message(chat_id, f"Raciocínio: {thinking}", channel="analysis")
            # Limpar a resposta final
            clean_response = re.sub(r'<think>.*?</think>\s*', '', full_response, flags=re.DOTALL).strip()
            if clean_response != full_response:
                full_response = clean_response

    # 6. Salvar resposta
    if full_response:
        await core.save_message("assistant", full_response, project_id=project_id)

    # 7. Auto-detect fatos
    if full_response and intent == "chat":
        asyncio.create_task(_auto_detect_memory(text, router))

    # 8. Auto-reflexão silenciosa
    if full_response and _reflect_enabled:
        asyncio.create_task(_auto_reflect(text, full_response, router))

    # 9. Compactação
    working_memory = await core.get_conversation(project_id=project_id)
    if len(working_memory) >= config.MAX_WORKING_MEMORY:
        await hooks.on_pre_compact(working_memory)
        logger.info(f"📦 Compactando working memory ({len(working_memory)} msgs)...")
        summary_messages = [
            {"role": "system", "content": "Resuma em 2-3 frases:"},
            *conversation,
        ]
        summary = await router.generate(summary_messages)
        if isinstance(summary, str):
            await core.compact_working_memory(summary, project_id=project_id)


async def _auto_detect_memory(user_text: str, router: LLMRouter):
    """Detecta fatos pessoais na mensagem do Criador (background)."""
    try:
        result = await router.generate([
            {"role": "system", "content": (
                "Analise a mensagem. Se contém um FATO PESSOAL importante "
                "(preferência, hobby, nome, profissão, projeto), "
                "extraia em uma frase curta. Se NÃO, responda: NENHUM\n"
                "Exemplos: 'Eu moro em SP' → 'Mora em São Paulo' | 'oi' → NENHUM"
            )},
            {"role": "user", "content": user_text},
        ], temperature=0.0)

        if isinstance(result, str) and "NENHUM" not in result.upper():
            fact = result.strip().strip('"').strip("'")
            if 5 < len(fact) < 200:
                await core.save_core_fact("auto", fact)
                logger.info(f"🧠 Auto-memorizado: {fact}")
    except Exception as e:
        logger.debug(f"Auto-detect falhou (ok): {e}")


async def _auto_reflect(user_text: str, response: str, router: LLMRouter):
    """Avalia a qualidade da própria resposta (background, silencioso)."""
    try:
        result = await router.generate([
            {"role": "system", "content": (
                "Avalie esta resposta de IA a uma mensagem do usuário.\n"
                "Critérios:\n"
                "1. Respondeu o que foi perguntado?\n"
                "2. Foi concisa ou enrolou?\n"
                "3. Inventou algum dado?\n"
                "4. O tom foi natural?\n\n"
                "Se tudo OK, responda: OK\n"
                "Se encontrou problema, responda com UMA lição curta de melhoria "
                "(máx 1 frase). Exemplo: 'Ser mais direta em perguntas simples'\n"
                "NÃO inclua explicações, só a lição."
            )},
            {"role": "user", "content": f"Pergunta: {user_text}\n\nResposta: {response[:500]}"},
        ], temperature=0.0)

        if isinstance(result, str) and "OK" not in result.upper().strip():
            lesson = result.strip().strip('"').strip("'")
            if 5 < len(lesson) < 150:
                await core.save_reflection(lesson)
                logger.info(f"🔍 Auto-reflexão: {lesson}")
    except Exception as e:
        logger.debug(f"Auto-reflect falhou (ok): {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Reminder Loop — Verifica lembretes pendentes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _reminder_loop():
    """Verifica lembretes pendentes a cada 30 segundos."""
    await asyncio.sleep(10)  # espera bot iniciar
    logger.info("⏰ Reminder loop iniciado")
    while True:
        try:
            pending = await core.get_pending_reminders()
            for r in pending:
                if _reminder_chat_id:
                    msg = f"⏰ **Lembrete:** {r['message']}"
                    await telegram_bot.send_simple_message(_reminder_chat_id, msg)
                    await core.mark_reminder_sent(r["id"])
                    logger.info(f"⏰ Lembrete #{r['id']} enviado: {r['message']}")
        except Exception as e:
            logger.debug(f"Reminder loop erro: {e}")

        await asyncio.sleep(30)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Preference Learning & Proactive Alerts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_last_preference_check_count = 0
_last_battery_alert = None
_last_weather_alert = None


async def _proactive_alerts_loop():
    """Monitora a saúde do sistema e do hardware. Alerta via Telegram se houver problema."""
    global _reminder_chat_id, _last_battery_alert, _last_weather_alert
    await asyncio.sleep(20) # Começa as checagens 20s após iniciar
    logger.info("🛡️ Proactive alerts loop iniciado (Monitoramento de Bateria)")

    while True:
        try:
            if _reminder_chat_id: # Só alerta se tivermos um chat registrado
                status_data = await core.get_system_status()
                # Procurar por sinais de bateria fraca nas strings de status
                # status_data retorna algo como "IARA (Master):\n  Bateria: 85% ..."
                
                # Vamos simplificar pegando as porcentagens
                import re
                bateria_matches = re.finditer(r'Bateria:\s*(\d+)%', status_data)
                
                for match in bateria_matches:
                    nivel = int(match.group(1))
                    
                    # Limiar provisório de 15%
                    if nivel <= 15:
                        agora = datetime.now()
                        # Não ficar enviando toda hora, alertar a cada 3 horas
                        if not _last_battery_alert or (agora - _last_battery_alert).total_seconds() > (3 * 3600):
                            await telegram_bot.send_simple_message(
                                _reminder_chat_id, 
                                f"⚠️ **Alerta Proativo de Bateria:**\n"
                                f"Detectei um nível crítico de energia ({nivel}%).\nPor favor, conecte o carregador."
                            )
                            _last_battery_alert = agora
                            logger.warning(f"🔋 Alerta de bateria enviado (Nível: {nivel}%)")

                # ==========================================
                # Alertas Proativos de Clima (Chuva Iminente)
                # ==========================================
                weather_data = await core.get_weather()
                if "Chuva" in weather_data or "Pancadas" in weather_data or "Temporal" in weather_data:
                    agora = datetime.now()
                    # Enviar alerta de chuva no máximo a cada 6 horas
                    if not _last_weather_alert or (agora - _last_weather_alert).total_seconds() > (6 * 3600):
                        await telegram_bot.send_simple_message(
                            _reminder_chat_id, 
                            f"🌧️ **Alerta Proativo de Clima:**\n"
                            f"Há previsão de chuva para hoje!\nDetalhes: {weather_data}"
                        )
                        _last_weather_alert = agora
                        logger.warning(f"🌧️ Alerta de chuva enviado!")

        except Exception as e:
            logger.debug(f"Erro no alerts loop: {e}")

        # Checa a cada 15 minutos (900s) para não floodar as APIs
        await asyncio.sleep(900)




async def _preference_learning_loop():
    """
    A cada 30 min verifica se acumulou 10+ episódios novos.
    Se sim, analisa padrões recorrentes e salva na core memory.
    Versão conservadora: só salva padrões com 3+ ocorrências.
    """
    global _last_preference_check_count
    await asyncio.sleep(60)  # espera bot estabilizar
    logger.info("🧠 Preference learning loop iniciado")

    while True:
        try:
            current_count = await core.get_episode_count()

            # Só analisa se acumulou 10+ episódios novos
            if current_count - _last_preference_check_count >= 10:
                logger.info(f"🧠 Analisando preferências ({current_count} episódios)...")

                # Pegar todos os episódios recentes
                episodes = await core.get_all_episodes(limit=20)
                existing_facts = await core.get_core_memory_text()

                if episodes:
                    episodes_text = "\n".join([f"- {ep}" for ep in episodes])

                    result = await router.generate([
                        {"role": "system", "content": (
                            "Analise esses resumos de conversas e extraia PADRÕES RECORRENTES sobre o usuário. "
                            "REGRAS ESTRITAS:\n"
                            "1. Só extraia padrões que aparecem 3+ vezes nos resumos\n"
                            "2. Ignore tópicos que apareceram apenas uma vez\n"
                            "3. Foque em: interesses, hábitos, horários, preferências, projetos\n"
                            "4. Formato: uma preferência por linha, curta e factual\n"
                            "5. Se não há padrões claros, responda APENAS: NENHUM\n\n"
                            f"Fatos que JÁ EXISTEM na memória (NÃO repita esses):\n{existing_facts}\n\n"
                            f"Resumos das últimas conversas:\n{episodes_text}"
                        )},
                    ], temperature=0.0)

                    if isinstance(result, str) and "NENHUM" not in result.upper():
                        # Parsear cada linha como uma preferência
                        new_prefs = [
                            line.strip().lstrip("-•").strip()
                            for line in result.strip().split("\n")
                            if line.strip() and len(line.strip()) > 5 and len(line.strip()) < 200
                        ]

                        saved = 0
                        for pref in new_prefs[:5]:  # Máximo 5 por batch
                            # Verificar se não é duplicata
                            if pref.lower() not in existing_facts.lower():
                                await core.save_core_fact("preferência", pref)
                                saved += 1

                        if saved > 0:
                            logger.info(f"🧠 {saved} preferências aprendidas!")

                _last_preference_check_count = current_count

        except Exception as e:
            logger.debug(f"Preference learning erro: {e}")

        await asyncio.sleep(1800)  # 30 minutos


async def _heartbeat_and_compaction_loop():
    """Executa heartbeat e compactação da memória de trabalho a cada 10 minutos."""
    await asyncio.sleep(60) # Espera inicial
    logger.info("🗑️ Heartbeat + Compaction loop iniciado")
    while True:
        try:
            # Limpeza de uploads antigos (72 horas)
            import time
            uploads_path = "uploads"
            if os.path.exists(uploads_path):
                now = time.time()
                for filename in os.listdir(uploads_path):
                    filepath = os.path.join(uploads_path, filename)
                    if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 72 * 3600:
                        try:
                            os.remove(filepath)
                            logger.info(f"🧹 Upload antigo removido: {filename}")
                        except Exception as delete_error:
                            logger.debug(f"Erro ao remover {filename}: {delete_error}")

            working_memory = await core.get_working_memory()
            if len(working_memory) >= config.MAX_WORKING_MEMORY:
                logger.info(f"🗑️ Compactando working memory ({len(working_memory)} msgs)...")
                summary_messages = [
                    {"role": "system", "content": "Resuma em 2-3 frases:"},
                    *working_memory,
                ]
                summary = await router.generate(summary_messages)
                if isinstance(summary, str):
                    await core.compact_working_memory(summary)
            else:
                logger.info("🗑️ Heartbeat: memória dentro do limite, sem necessidade de compactação.")
        except Exception as e:
            logger.debug(f"Erro no heartbeat: {e}")

        await asyncio.sleep(600)  # roda a cada 10 min

async def _worker_health_loop():
    """Ping contínuo nos workers registrados para saber quem está online."""
    await asyncio.sleep(10)  # Espera inicial
    logger.info("🐝 Worker Health Loop iniciado")
    while True:
        try:
            await worker_protocol.health_check()
        except Exception as e:
            logger.debug(f"Erro no health check dos workers: {e}")
        
        await asyncio.sleep(60) # Checa a cada 1 minuto

async def _run_consolidation(chat_id=None):
    """Lógica pesada de consolidação."""
    logger.info("🌌 Iniciando Nightly Memory Consolidation...")
    if chat_id:
        await telegram_bot.send_simple_message(chat_id, "🌌 Consolidando episódios antigos...")
        
    episodes = await core.get_unprocessed_episodes(limit=30)
    if not episodes:
        logger.info("🌌 Sem episódios antigos para consolidar.")
        if chat_id: await telegram_bot.send_simple_message(chat_id, "Nenhum episódio pra consolidar.")
        return
        
    ep_text = "\n".join([f"[{e['timestamp']}] {e['summary']}" for e in episodes])
    existing_core = await core.get_core_memory_text()
    
    prompt = f"""Você é o subsistema de consolidação de memórias da IARA.
Seu trabalho é ler um lote de resumos antigos de conversas e extrair FATOS PERMANENTES sobre o usuário ou sobre a própria Iara que devem ser lembrados para sempre.

Regras:
1. Extraia apenas fatos importantes (preferências, medos, rotinas, dados fixos). Ignore conversas triviais.
2. Cada fato deve ser uma frase curta e direta (ex: "O usuário odeia pizza de abacaxi").
3. Não repita fatos que já estão na Core Memory atual.
4. Responda APENAS com a lista de novos fatos, um por linha, começando com '- '. Se não houver nada útil, responda 'NADA'.

Core Memory Atual:
{existing_core}

Lote de Episódios:
{ep_text}
"""
    result = await router.generate([{"role": "user", "content": prompt}], temperature=0.1)
    
    facts_saved = 0
    if isinstance(result, str) and "NADA" not in result.upper():
        lines = [line.lstrip("- ").strip() for line in result.split("\n") if line.strip().startswith("-")]
        for fact in lines:
            if fact:
                await core.save_core_fact("consolidado", fact)
                facts_saved += 1
                
    # Deleta os episódios já processados pra não crescer infinito
    ids_to_del = [e["id"] for e in episodes]
    await core.delete_old_episodes(ids_to_del)
    
    msg = f"🌌 Consolidação concluída! {len(episodes)} episódios apagados. {facts_saved} novos fatos permanentes aprendidos."
    logger.info(msg)
    if chat_id: await telegram_bot.send_simple_message(chat_id, msg)

async def _memory_consolidation_loop():
    """Roda todo dia de madrugada (03:00) para processar os episódios e limpar o DB."""
    await asyncio.sleep(120)  # Espera inicial
    logger.info("🌌 Nightly Memory Consolidation Loop iniciado")
    while True:
        try:
            now = datetime.now()
            # Roda entre as 03:00 e 04:00 da manhã
            if now.hour == 3:
                await _run_consolidation()
                # Dorme 2 horas pra garantir que não vai processar de novo hoje
                await asyncio.sleep(7200)
                continue
        except Exception as e:
            logger.error(f"Erro na consolidação de memórias: {e}")
            
        await asyncio.sleep(3600)  # Checa a cada hora se deu a hora

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Inicialização
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def send_proactive_message(markdown_text: str):
    """
    Função de injenção de mensagens proativas (para o Scheduler Autônomo).
    Atua como Wrapper assíncrono pro telegram_bot.send_message.
    """
    chat_id = config.TELEGRAM_CHAT_ID if hasattr(config, "TELEGRAM_CHAT_ID") else config.USER_ID_ALLOWED
    await telegram_bot.send_message(chat_id=chat_id, text=markdown_text)

async def main():
    """Inicializa tudo e inicia o bot."""
    logger.info("🌊 Iara está acordando...")

    # Phase 15: Validar configs e alertar sobre degradação de features
    config.validate_config()

    await core.init_db()
    logger.info("✅ Memória inicializada")
    
    try:
        # Iniciamos o processo de backup como não-bloqueante para testar credenciais
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "backup_drive.py",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        logger.info("☁️ Verificação do Google Drive iniciada em background...")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível testar o backup: {e}")
        
    # Recuperar jobs do swarm que podem ter sido interrompidos
    await orchestrator.load_pending_jobs()

    status = router.get_status()
    logger.info(f"🧠 LLMs ativos: {status['providers_ativos']}")

    telegram_bot.set_message_handler(process_message)
    logger.info("✅ Telegram configurado")

    # Inicializa serviços agendados
    asyncio.create_task(_reminder_loop())
    asyncio.create_task(_preference_learning_loop())
    asyncio.create_task(_proactive_alerts_loop())
    asyncio.create_task(_worker_health_loop())
    asyncio.create_task(_heartbeat_and_compaction_loop())
    asyncio.create_task(_memory_consolidation_loop())
    
    # Phase 14: Popular Banco Virgem de Jobs e Iniciar Loop Autônomo
    jobs_db = await core.get_all_scheduled_jobs()
    if not jobs_db:
        await core.add_scheduled_job("morning_briefing", "08:00", "morning_briefing", enabled=False)
        await core.add_scheduled_job("session_end_hook", "23:30", "session_end_hook", enabled=False)
        logger.info("📅 Jobs autônomos padrão criados e prontos para ativação.")
        
    asyncio.create_task(scheduler.start_scheduler(send_proactive_message))

    # Executa Hook de inicialização
    await hooks.on_session_start(0)

    # Iniciar Dashboard Web
    logger.info("🌐 Iniciando Dashboard Web (FastAPI) na porta 8080...")
    threading.Thread(target=dashboard_api.run_dashboard, daemon=True).start()

    logger.info("🌊 Iara está online! Esperando mensagens...")
    await telegram_bot.start_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🌊 Iara dormindo... Até logo!")
        sys.exit(0)
