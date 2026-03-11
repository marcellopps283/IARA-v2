# 🚀 Migração Iara: Termux → VPS Google Cloud

> **VPS**: 2 núcleos, 8GB RAM (Google Cloud)
> **Objetivo**: Melhor versão da Iara possível, abusando de APIs gratuitas e GitHub Student Pack

---

## 🔓 O que desbloqueia saindo do Termux

### 1. Embeddings Locais (sem API)
- No Termux: dependência do Cohere API para RAG semântico
- Na VPS: rodar **`sentence-transformers`** localmente (ex: `all-MiniLM-L6-v2`, ~90MB RAM)
- **Resultado**: busca semântica infinita e gratuita, sem gastar cota

### 2. Vector Store Real (ChromaDB / Qdrant)
- Em vez do SQLite puro pra memória, subir um **ChromaDB** (mais leve) ou **Qdrant**
- Memória de longo prazo com busca por similaridade semântica de verdade
- Não mais limitada a busca por data ou keyword

### 3. MCP Servers Nativos
- No Termux: MCP Client usava REST custom por limitações de compilação C
- Na VPS Linux: **SDK oficial do MCP** com JSON-RPC 2.0 nativo, stdio transport

### 4. Dashboard Sempre Online (24/7)
- FastAPI + Uvicorn rodando sem matar bateria
- **Nginx reverse proxy** na frente (ou Nginx Proxy Manager já existente na VPS)
- Dashboard exposto com HTTPS e domínio próprio

### 5. Agendador Real (systemd + cron)
- Em vez do `scheduler.py` com `asyncio.sleep`
- Iara como **systemd service**: reinicia automaticamente se crashar
- Cron nativo pra backups e heartbeats

### 6. Sandbox de Código Local (Docker)
- O E2B cobra por uso
- Na VPS: **Docker containers** pra sandboxing local gratuito e infinito
- Execução de código isolada sem custo

---

## 🎓 GitHub Student Pack — Recursos para Abusar

| Recurso | Como usar na Iara |
|---|---|
| **GitHub Copilot** | Desenvolvimento mais rápido |
| **GitHub Codespaces** | Ambiente de dev cloud auxiliar |
| **Domínio grátis (.me via Namecheap)** | `iara.seudominio.me` pro dashboard |
| **MongoDB Atlas credits** | Migração de SQLite pra DB mais robusto (se necessário) |
| **DigitalOcean credits ($200)** | VPS extra ou CDN |
| **Sentry** | Monitoramento de erros em produção (crash reporting) |
| **DataDog** | Observabilidade (métricas de latência dos LLMs, uso de memória) |

---

## 🧠 Melhorias de Arquitetura Viáveis na VPS

### 1. LLM Router com Métricas Dinâmicas
- Gravar latência, taxa de erro e custo de cada provider
- Usar métricas reais para scoring dinâmico em vez de scores fixos no código
- Auto-ajuste: providers mais rápidos/confiáveis sobem na prioridade automaticamente

### 2. WebSocket no Dashboard
- Streaming real via **WebSocket** em vez de SSE
- Mais estável e bidirecional
- Permite push de notificações do servidor pro cliente

### 3. Multi-Projeto com Isolamento Real
- Cada projeto com seu próprio namespace de memória
- Conversation history isolado por projeto
- Vector store separado por contexto

### 4. Pipeline de Deep Research Melhorado
- Com mais RAM: processar documentos maiores
- Manter mais contexto simultâneo
- Síntese multi-fonte mais robusta e profunda

### 5. Cache de Respostas LLM
- **Redis** ou cache em SQLite pra não refazer chamadas idênticas
- Economia significativa de cota de API
- Respostas instantâneas para perguntas repetidas

### 6. Webhook do Telegram (em vez de Polling)
- Atualmente: `dp.start_polling` (puxa mensagens periodicamente)
- Na VPS com IP fixo + HTTPS: usar **webhook** (Telegram envia direto)
- Mais eficiente, mais rápido, menos consumo de recursos

---

## ✅ O que MANTER do Setup Atual

| Componente | Motivo |
|---|---|
| **aiohttp puro (sem SDK pesado)** | Leve, portável, funciona perfeitamente |
| **Sistema de fallback multi-LLM** | Gold — resiliência total |
| **Hooks de segurança** | Essencial — proteção contra vazamento de chaves |
| **Estrutura modular** (brain, core, router, telegram, dashboard) | Já está bem organizada |
| **Guardrails e HITL Policy** | Kill switch financeiro e controle de cota |

---

## 📋 Resumo das APIs Gratuitas em Uso

| Provider | Modelo | Uso Principal |
|---|---|---|
| **Groq** (x2 chaves) | Llama 3.3 70B | Chat principal + fallback |
| **Cerebras** (x2 chaves) | Llama 3.1 8B | Fast tasks |
| **OpenRouter** | DeepSeek R1 | Reasoning complexo |
| **NVIDIA NIM** | Kimi K2.5 | Research (contexto longo) |
| **Gemini** | Gemini 2.5 Flash | Visão + Embeddings (atual) |
| **Mistral** | Mistral Large | Código + fallback |
| **Cohere** | — | RAG semântico (substituível por local) |
| **E2B** | — | Sandbox (substituível por Docker) |
| **SambaNova** | — | Disponível como extra |
