# 🧠 IARA v2: Master Roadmap & Architectural Implementation Plan
> **Target Audience:** Artificial Intelligence Agents & Orchestrators
> **System Philosophy:** ZeroClaw (Organic, Autonomous, Local-First)

Este documento descreve a trajetória técnica da IARA v2, desde sua concepção como um assistente reativo até sua evolução final como uma Agência Autônoma de 17 Fases. Ele é projetado para que modelos de linguagem (LLMs) possam analisar dependências, identificar gargalos e propor refatorações proativas.

---

## 🏗️ Core Architecture: The "Triple Layer" Pattern

O sistema opera em um padrão de **Orquestração de Grafos (LangGraph)**, onde o fluxo de pensamento é fragmentado em nós de decisão:
1.  **Semantic Router Layer**: Classificação de intenção via embeddings locais (ONNX INT8).
2.  **Memory Layer (Trinity)**: 
    - `Working`: Short-term (Redis/RAM).
    - `Episodic`: Mid-term summaries (Mem0/Qdrant).
    - `Core`: Permanent facts (Mem0/LightRAG/Knowledge Graph).
3.  **Execution Layer (Swarm/Council)**: Especialistas assíncronos e debate adversarial.

---

## 🗺️ Roadmap de 17 Fases (The Evolution Path)

### 🟢 Ciclo 1: Fundação & Estabilização (Fases 1-6)
*Foco: Sair da restrição do Termux/Android e ganhar liberdade de processamento na VPS.*

- **Fase 1: Bootstrap & Webhook**: Migração de polling (lento) para Webhook (instatâneo) via FastAPI e Nginx Proxy Manager.
- **Fase 2: Multi-LLM Routing**: Implementação do roteador com sistema de pooling e fallback (Groq, Sambanova, Gemini).
- **Fase 3: Local Vector Store**: Setup do **Qdrant** nativo para evitar custos e limites de APIs de terceiros.
- **Fase 4: Infrastructure-as-Code**: Dockerização total (Postgres, Redis, Qdrant, Infinity).
- **Fase 5: Atomic Skills**: Modularização de ferramentas em scripts plug-and-play.
- **Fase 6: Persona Calibration**: Engenharia de prompt baseada no `SOUL.md` para consistência comportamental.

### 🟡 Ciclo 2: Raciocínio & Performance (Fases 7-9)
*Foco: Implementar estado, memória profunda e velocidade de resposta.*

- **Fase 7: Graph Orchestration**: Transição para **LangGraph**, permitindo fluxos cíclicos e recuperação de erros.
- **Fase 8: Deep Memory (Mem0 + LightRAG)**: 
    - Integração de grafos de conhecimento para entender relações complexas.
    - Implementação de resolução de contradições em tempo real.
- **Fase 9: Dashboard & Performance**:
    - **9.1**: Interface Web para monitoramento de tokens e logs.
    - **9.2 (Performance Blitz)**: Quantização **ONNX INT8** do modelo de embedding, cache semântico no Redis e paralelização asíncrona de I/O de memória.

### 🔵 Ciclo 3: Agência e Ação (Fases 10-14)
*Foco: Capacidade de interagir com o mundo e agir sobre o ambiente.*

- **Fase 10: Coder Node (Sandbox Arena)**: 
    - **Processo**: Agente gera código -> Envia para container Docker efêmero -> Valida output -> Integra resultado.
    - **Segurança**: Isolamento total do HOST via gVisor ou Docker Bridge restrita.
- **Fase 11: Massive Parallelism**: Execução simultânea de processos de decisão (Council e Swarm) para reduzir o TIME TO FIRST TOKEN (TTFT).
- **Fase 12: Project Isolation (N-Project Architecture)**: 
    - Escalonamento para gerenciar vários "negócios" ou "ideias" sem confusão semântica (namespaces de memória).
- **Fase 13: Multimodal Vision**: Integração de fluxos de imagem (Gemini 2.0 Vision) para permitir que a IARA "veja" o que está acontecendo no computador ou servidor.
- **Fase 14: Background Autonomous Scheduler**:
    - Implementação de tarefas `CRON` dentro do LangGraph.
    - A IARA pode decidir realizar um backup ou uma pesquisa de mercado enquanto o usuário dorme.

### 🟣 Ciclo 4: Auto-Evolução & Maturidade (Fases 15-17)
*Foco: Autonomia total e otimização de borda.*

- **Fase 15: Self-Healing Logic**:
    - O Agente analisa tracebacks de falhas de ferramentas e reescreve seu próprio "plano de voo" para contornar o erro sem pedir intervenção humana.
- **Fase 16: Mobile Edge Workers (S21/MotoG4)**: 
    - Uso dos celulares via SSH como workers de baixo custo para tarefas de scraping residencial (bypass de Cloudflare via IPs móveis).
- **Fase 17: Dynamic MCP Registry**:
    - Injeção a quente de novos servidores MCP. A IARA pode "aprender" uma nova ferramenta apenas baixando um manifesto JSON-RPC.

---

## 🛠️ Instruções para Análise de IA
Ao analisar este roadmap em conjunto com o código atual:
1.  **Dependências**: Verifique se a Fase 12 (Project Isolation) requer refatoração do `memory_manager.py` para suportar `project_id` em todas as queries.
2.  **Otimização**: Avalie se o uso de `asyncio.gather` na Fase 11 criará condições de corrida (Race Conditions) no acesso ao SQLite.
3.  **Segurança**: Para a Fase 10, proponha a arquitetura de volumes Docker que minimize o risco de ESCAPE DO CONTAINER.

---
*Status Document: v2.1.0*
*Assinado: Cérebro Coletivo IARA.*
