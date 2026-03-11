# IARA Ecosystem (ZeroClaw-inspired) — Especificação Técnica Consolidada

Este documento define a arquitetura, os objetivos e as diretrizes de implementação para o "Reboot" do projeto IARA. O objetivo é migrar de um ambiente Android/Termux restrito para uma VPS Linux robusta, mantendo a filosofia orgânica do ZeroClaw, mas alcançando autonomia real, sem dependência de plataformas "caixa-preta".

---

## 1. Visão Geral e Objetivos Principais

O sistema será uma **Sociedade de Agentes** autônoma e inteligente, projetada para contornar limitações de limites de cota (rate limits) e operar com máxima eficiência de custos.

*   **Independência de Cota:** Roteador inteligente de LLMs (Groq, Sambanova, Cerebras, Mistral, Gemini, OpenRouter) operando com sistema de pooling e fallbacks automáticos.
*   **Memória Semântica Local:** Implantação de embeddings locais (`sentence-transformers`) e um Vector Store nativo na VPS (`ChromaDB` ou `Qdrant`) para busca escalável sem custos de API.
*   **Auto-evolução:** Agentes capazes de escrever, testar (em Sandbox Python/Docker) e aprimorar seus próprios códigos e instruções (SOPs).
*   **Liberdade e Transparência:** Controle absoluto sobre o loop de raciocínio. Nada de "caixas pretas" como o OpenClaw; o código de orquestração deve ser acessível e preferencialmente em Python puro.

---

## 2. Arquitetura-Alvo (MoE + Assistente Central)

A estrutura operará sob o paradigma de Mistura de Especialistas (Mixture of Experts - MoE) orquestrada e distribuída:

*   **IARA (Assistente Central / Orquestrador):** A "mente" governante. Foca em gerenciar o contexto do usuário, manter o estado/memória, iniciar a execução de especialistas e sintetizar respostas. Delega tarefas sempre que a sua própria execução não for a mais otimizada.
*   **Swarm de Especialistas:** Sub-agentes assíncronos (Coder, Researcher, Memory, Planner, Watchdog, etc.), cada um com suas ferramentas e SOPs próprios.
*   **Council (Conselho Deliberativo):** Para decisões críticas e arquiteturais. A IARA atua como juíza de um debate onde diferentes agentes propõem soluções, criticam uns aos outros e convergem em uma síntese (Rodada 1 -> Rebuttal -> Síntese).
*   **Infraestrutura Distribuída (VPS + Dispositivos Físicos):** 
    *   **VPS (8GB RAM):** Sede da orquestração principal (LangGraph), memória vetorial (ChromaDB) e execução de sandboxes seguras (Docker).
    *   **Smartphones (S21/Mobile):** Nós periféricos de exploração (Workers). Usam IPs residenciais/móveis, excelentes para scraping web stealth (evasão anti-bot) e coleta de dados sensíveis na internet.

---

## 3. Stack Tecnológico e Frameworks (A Convergência)

Para equilibrar o controle total com capacidades avançadas de orquestração de falhas, o ecossistema será construído utilizando uma combinação estratégica:

*   **LangGraph (Orquestração Macro):** Responsável por gerenciar os estados, loops, `Council` e checkpoints de memória. Transforma as ações em grafos rastreáveis e auditáveis.
*   **SmolAgents / Python Puro (Micro-Agentes):** Especialistas individuais, controlados e construídos em código 100% Pythonístico e auditável, garantindo que o loop interno e as ferramentas sejam plenamente governáveis por você e pela própria IARA.
*   **AutoGen (Sandbox / Opcional):** Como módulo utilitário para gerenciamento nativo da execução segura de código dentro de containers locais Docker.

---

## 4. Estratégia de Chaves e Load Balancing

O gargalo atual não é a capacidade dos LLMs, mas a disputa por cotas (Rate Limits).

*   **Pools por Papel:** Agentes específicos recebem chaves/níveis específicos. A IARA Core usa modelos potentes; o Red Team/Tester pode usar instâncias rápidas baseadas no Llama; pesquisadores rasos usam chaves auxiliares.
*   **Fallback Dinâmico Integrado:** Um Roteador Interno ou Proxy local que percebe o erro `429 (Too Many Requests)` e realiza fallback instantâneo/round-robin (usando suas múltiplas chaves providas) para manter a linha de montagem assíncrona fluindo com zero downtime perceptível.

---

## 5. Validação de Código e Arena Adversarial

Sistemas orgânicos falham se as IAs se comportarem de forma complacente com seus resultados ("parece bom o suficiente").

*   **Blue Team (O Construtor):** Escreve as features principais e lógicas (ex: `SmolAgent` de Código).
*   **Red Team (O Destruidor):** Focado puramente em quebrar. Cria testes unitários contraintuitivos, injeta edge cases e testa vulnerabilidades (ex: injetar valores nulos inesperados).
*   **A "Arena" (Docker Sandbox VPS):** O código flui para a VPS, liga-se os testes do Red Team com a construção do Blue Team. Falhou? O Stack Trace volta silenciosamente para o Blue Team corrigir. A IARA/Usuário só recebem o relatório após a conclusão ou após o teto limite de iterações ser exaurido.

---

## 6. Interface Homem-Máquina (UX via Telegram e Streaming)

A governança do ecossistema não deve poluir a conversa, e vice-versa. Utilizaremos o esquema vencedor de duplos canais:

*   **Bot de Conversa (Usuário <> Iara):** Conversação humanizada, polida, baseada no `soul.md`. As tarefas complexas utilizam *streaming retroativo* (edição progressiva da mesma mensagem com estados: `"Transcrevendo..."` → `"Delegando..."` → `"Executando..."` → Resultado).
*   **Bot Operacional (Control Room):** Grupo privado, invisível ao usuário corriqueiro, que apita com diffs, logs de terminal, crash logs do Docker e alertas do Orquestrador.

---

## 7. Transparência Dinâmica, SOPs e Versionamento

O sistema nunca será uma "caixa-preta". A flexibilidade impera sobre tudo.

*   **Pastas Visíveis:** O cérebro será materializado em arquivos legíveis (`soul.md`, `sop.md`, `memory.md`) armazenados por pasta de agente localmente.
*   **Git como Memória de Alteração:** O sistema usa Git nativo na VPS. Sempre que a IARA auto-atualizar os SOPs a partir do "aprendizado" de uma falha, ela realiza um *commit* automático. 
*   **Acesso Mestre / PR Interno:** Qualquer modificação feita pelas IAs tem um rastro (diff) gerado e emitido para o *Bot de Logs*.
*   **Dashboard Local (v0.dev + FastAPI):** Para conveniência, pode-se levantar de fundo um painel web que lista rapidamente os arquivos da mente de todos os agentes para a edição manual do usuário a qualquer momento (bypass supremo).
