# Contexto Arquitetural: Projeto IARA (KittyClaw / ZeroClaw)
> **Aviso para Inteligências Artificiais:** Leia este documento antes de propor refatorações arquiteturais, adicionar bibliotecas pesadas ou modificar a topologia de rede.

Este projeto não é uma aplicação web ou um script Python comum rodando em um servidor em nuvem (AWS/GCP). É um sistema multi-agente avançado rodando **nativamente em smartphones Android** utilizando o ambiente **Termux**.

## 1. Topologia de Hardware (O "Swarm")

O sistema é distribuído através de uma rede Wi-Fi local entre três dispositivos físicos com papéis bem definidos:

1.  **S21 Ultra (Master / "IARA"):** 
    *   **Papel:** Orquestrador principal, cérebro do sistema, hospeda o servidor Vite (Frontend) e o FastAPI (Dashboard API). 
    *   **Restrições:** Deve ser preservado a todo custo. Cargas de trabalho intensas (processamento paralelo pesado) devem ser delegadas para evitar sobrecarga de RAM e CPU neste aparelho, pois ele também roda o jogo MMRPG "KittyClaw" do usuário em background.
2.  **S21 FE (Heavy Worker / Prioridade 1):**
    *   **Papel:** Processamento bruto de tarefas delegáveis via Swarm.
    *   **Ambiente:** Acessado via SSH (`KittyFE`).
3.  **Moto G4 (Light Worker / Prioridade 2 - Fallback):**
    *   **Papel:** Processamento de tarefas de baixa prioridade caso o FE esteja ocupado.
    *   **Ambiente:** Acessado via SSH (`MotoG4`).
    *   **Restrições:** Hardware obsoleto e bateria viciada. Mantido continuamente na tomada para não desligar. Processos pesados não devem ser enviados para cá.

## 2. Restrições do Ambiente (Termux)

O Termux é um emulador de terminal Linux para Android, mas **não** é uma distribuição Linux padrão (como Ubuntu/Debian).

*   **File System:** O caminho raiz não é `/`, mas sim `/data/data/com.termux/files/usr`.
*   **LIBC:** O Termux usa a Bionic libc do Android, não a Glibc padrão. Binários compilados para Linux padrão (ex: bibliotecas C estendidas, alguns pacotes do Node/Python pesados) geralmente **falharão** ou darão *Segmentation Fault*.
*   **Node.js/Python:** Já estão instalados nativamente via `pkg install`, evite sugerir o uso de ferramentas como `nvm` ou `pyenv` que tentam baixar binários pré-compilados do Linux.
*   **Gerenciamento de Processos:** Em vez de usar `systemd`, o gerenciamento de daemons/serviços é feito via `pm2` ou controle manual de subprocessos.
*   **Doze Mode (Android):** O sistema operacional Android é agressivo ao suspender processos em background para economizar bateria. Conexões SSH entre os aparelhos requerem *KeepAlive* constante para não sofrerem timeout forçado pelo kernel do Android.

## 3. Decisões Arquiteturais Críticas (NÃO ALTERAR)

1.  **SQLite sobre PostgreSQL/MySQL:** Devido às restrições do Termux e ao consumo de RAM em celulares, todo o estado, histórico de jobs do Swarm e memória episódica/core da IARA são salvos em SQLite (`kitty_memory.db`).
2.  **Frontend Vite:** O frontend PWA (Interface estilo v0.dev) é servido pelo Vite localmente no S21 Ultra e acessado via rede local (192.168.x.x) pelo computador do usuário. NÃO sugira migrar para Next.js nativo no Termux, pois a compilação pesada do Next.js sobrecarregaria o celular Master de forma imprudente.
3.  **Filas Customizadas (Sem RabbitMQ/Redis):** O orquestrador de tarefas (Swarm) usa um sistema de filas personalizado e assíncrono escrito em Python puro (`orchestrator.py` e `transport.py`) com base no SQLite e SSH, consumindo menos de 10MB de RAM. Não sugira Redis, Kafka ou Celery.
4.  **Loop Contínuo:** A IARA roda em um loop principal assíncrono (`brain.py`). Qualquer operação síncrona/bloqueante (I/O intensivo) derrubará as respostas do WebSocket do frontend.

## 4. O Sistema "Persona" e "Skills"

*   **Personas (`roles/`):** Arquivos Markdown que ditam o comportamento de agentes secundários (ex: Pesquisador, Revisor).
*   **Skills (`skills/`):** Scripts Python plug-and-play que implementam lógicas atômicas (como leitura de arquivos, buscas na web ou conversão de PDF).
*   **Memory Core (`memory_core_skill.py`):** A IARA possui um loop inteligente de consolidação. Às 03h da manhã, o sistema resume o histórico diário em fatos essenciais para economizar os limites de contexto (tokens) nas próximas chamadas de LLM.

## 5. Ferramentas de Orquestração (Stateful Todo e PlanMode)

Para gerenciar o seu próprio fluxo de trabalho, a IARA tem comandos especiais que **você mesma (o LLM) pode escrever no chat** para alterar o estado do sistema e do usuário:

*   **Stateful Todo Machine:** Quando precisar coordenar múltiplas etapas, invoque as tarefas:
    *   `/task add [descrição]` - Para mapear o que fará.
    *   `/task start [ID]` - Para trabalhar naquela etapa (Só 1 in_progress por vez).
    *   `/task done [ID]` - Para concluir.

*   **PlanMode Lock:**
    *   Sempre use `/plan on` antes de iniciar a construção lógica de arquiteturas ou projetos grandes. O sistema avisará o usuário que a IARA está focada.  
    *   Depois de elaborar o Plano (`plan.md`) via agente, diga `/plan off` para destrancar a modificação primária no sistema e pedir aprovação formal.

---
*Assinado: Cérebro Coletivo IARA.*
