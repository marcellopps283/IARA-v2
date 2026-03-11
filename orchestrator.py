"""
orchestrator.py — Gerente Burocrático do Swarm (ZeroClaw)
Mantém fila de tarefas, prioriza o S21 FE e previne OOM no S21 Ultra.
Trabalha com Personas Estáticas pré-definidas na pasta /roles/.
"""

import asyncio
import logging
from typing import Dict, Any, List

import config
import worker_protocol
import core

logger = logging.getLogger("orchestrator")

# Tabela de controle de processos ativos (quantos agentes em cada nó)
_active_workers: Dict[str, int] = {
    "S21FE": 0,
    "KittyS21": 0  # S21 Ultra (Master overflow)
}

# Fila de espera global
_task_queue = asyncio.Queue()


class SwarmTask:
    def __init__(self, role_name: str, payload: str, callback=None, job_id: int = None):
        self.role_name = role_name
        self.payload = payload
        self.callback = callback  # Função para avisar a Iara quando a task terminar
        self.job_id = job_id  # Controle do SQLite para anti-crash


def _get_available_node() -> str | None:
    """Retorna o nó disponível com maior prioridade, ou None se tudo lotado."""
    # Prioridade 1: S21 FE
    workers = {w['name']: w for w in worker_protocol.get_workers()}
    
    if "S21FE" in workers and _active_workers["S21FE"] < config.MAX_WORKERS_S21FE:
        return "S21FE"
    
    # Prioridade 2: Ultra (transbordo)
    if _active_workers["KittyS21"] < config.MAX_WORKERS_ULTRA:
        return "KittyS21"
    
    return None


async def load_pending_jobs():
    """Chamado na inicialização para recuperar jobs perdidos em caso de crash (Amnésia)."""
    try:
        jobs = await core.get_pending_swarm_jobs()
        for job in jobs:
            task = SwarmTask(job['role_name'], job['payload'], None, job_id=job['id'])
            await _task_queue.put(task)
        if jobs:
            logger.info(f"♻️ Recuperados {len(jobs)} jobs perdentes do SQLite pós-crash!")
            asyncio.create_task(_process_queue())
    except Exception as e:
        logger.error(f"Erro ao recuperar fila do SQLite: {e}")

async def submit_task(role_name: str, payload: str, callback=None):
    """A Iara chama isso para jogar trabalho no Orquestrador."""
    # Persiste no SQLite primeiro
    job_id = await core.add_swarm_job(role_name, payload)
    
    task = SwarmTask(role_name, payload, callback, job_id=job_id)
    await _task_queue.put(task)
    logger.info(f"📋 Task '{role_name}' adicionada à fila DB-ID #{job_id} (Tamanho: {_task_queue.qsize()})")
    
    # Garante que o loop do orchestrator comece a esvaziar a fila se já não estiver
    asyncio.create_task(_process_queue())


async def _process_queue():
    """Inspeciona a fila e despacha para os workers disponíveis."""
    while not _task_queue.empty():
        target_node = _get_available_node()
        
        if not target_node:
            logger.warning("🧱 Enxame lotado (OOM Defense Ativado). Aguardando slots...")
            break  # Sai do processamento agora, será chamado de novo quando um worker liberar
        
        task: SwarmTask = await _task_queue.get()
        _active_workers[target_node] += 1
        
        logger.info(f"🚀 Deployando persona '{task.role_name}' no nó >>> {target_node} <<< (Job #{task.job_id})")
        
        if task.job_id:
            await core.update_swarm_job_status(task.job_id, 'processing')
        
        # Lança a execução desanexada
        asyncio.create_task(_execute_on_node(target_node, task))


async def _execute_on_node(node_name: str, task: SwarmTask):
    """Executa a tarefa no nó via worker_protocol SSH."""
    result = None
    status = "done"
    try:
        # Chama SSH pra acionar o run_task.py do worker com a persona específica
        result = await worker_protocol.dispatch_mini_agent(node_name, task.role_name, task.payload)
        
        if isinstance(result, str) and result.startswith("Falha"):
            status = "failed"
            
    except Exception as e:
        logger.error(f"❌ Erro executando mini-agente no {node_name}: {e}")
        result = f"Error: {e}"
        status = "failed"
    finally:
        # Registra sucesso ou falha no SQLite persistente
        if task.job_id:
            res_str = str(result)[:500] if result else ""
            await core.update_swarm_job_status(task.job_id, status, res_str)
            
        # Libera o slot do worker
        _active_workers[node_name] -= 1
        logger.info(f"🏁 Task #{task.job_id} concluída. Slot devolvido no {node_name}. Ativos lá: {_active_workers[node_name]}")
        
        if task.callback:
            await task.callback(result)
            
        # Como liberou espaço, tenta processar mais da fila
        asyncio.create_task(_process_queue())
