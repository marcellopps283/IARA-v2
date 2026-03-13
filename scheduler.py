"""
scheduler.py — IARA Background Autonomous Scheduler (Phase 14)
Handles proactive tasks like memory refinement, auto-audits, and system health checks.
"""

import asyncio
import logging
import json
from datetime import datetime
import importlib
import subprocess
import os

import memory
import brain
import memory_manager
import semantic_router

logger = logging.getLogger("scheduler")

class AutonomousScheduler:
    def __init__(self):
        self.running = False
        self._tasks = []

    async def start(self):
        """Starts the background scheduler loop."""
        if self.running:
            return
        self.running = True
        logger.info("🚀 IARA Background Scheduler Started")
        
        # Ensure memory backends (Redis + SQLite) are ready
        await memory.init()
        
        # Start the main loop (proactive audits)
        asyncio.create_task(self._main_loop())
        # Start high-frequency loops (SOTA 2026 Phase 15)
        asyncio.create_task(self._drift_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._memory_refinement_loop())

    async def stop(self):
        """Stops the scheduler."""
        self.running = False
        logger.info("🛑 IARA Background Scheduler Stopped")

    async def _main_loop(self):
        """Main loop that checks for pending jobs every hour (less frequent tasks)."""
        while self.running:
            try:
                # 3. Random Auto-Audit
                await self.task_auto_audit()
                
            except Exception as e:
                logger.error(f"❌ Scheduler loop error: {e}", exc_info=True)
            
            # Wait for 1 hour (or adjusted interval)
            # For now, let's keep it at 1 hour for background maintenance
            await asyncio.sleep(3600)

    async def _drift_loop(self):
        """Loop for high-frequency infrastructure drift checks (e.g., every minute)."""
        while self.running:
            try:
                await self.task_infra_drift_check()
            except Exception as e:
                logger.error(f"❌ Drift loop error: {e}", exc_info=True)
            await asyncio.sleep(60) # Check every minute

    async def _health_check_loop(self):
        """Loop for medium-frequency system health checks (e.g., every 5 minutes)."""
        while self.running:
            try:
                await self.task_health_check()
            except Exception as e:
                logger.error(f"❌ Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(300) # Check every 5 minutes

    async def _memory_refinement_loop(self):
        """Loop for medium-frequency memory refinement (e.g., every 10 minutes)."""
        while self.running:
            try:
                await self.task_memory_refinement()
            except Exception as e:
                logger.error(f"❌ Memory refinement loop error: {e}", exc_info=True)
            await asyncio.sleep(600) # Refine every 10 minutes

    async def task_memory_refinement(self):
        """
        Consolidates episodic memory into the knowledge graph and core memory.
        """
        logger.info("🧠 Task: Memory Refinement...")
        # Get unprocessed episodes (using memory wrapper for state control)
        episodes = await memory.get_unprocessed_episodes(limit=10)
        if not episodes:
            logger.debug("Checked: No new episodes to refine.")
            return

        processed_count = 0
        for ep in episodes:
            text = ep["summary"]
            # Ingest into Knowledge Graph (LightRAG)
            await memory_manager.ingest_knowledge_graph(text)
            
            # Mark as processed in SQLite to avoid infinite loop
            await memory.mark_episode_processed(ep["id"])
            processed_count += 1
            logger.debug(f"Ingested episode {ep['id']} into Knowledge Graph and marked as processed.")
            
        logger.info(f"✅ Refined {processed_count} memory episodes.")

    async def task_health_check(self):
        """Checks latency and status of key components."""
        logger.info("🌡️ Task: System Health Check...")
        # Check LLM Gateway
        router = brain.get_router()
        try:
            start = datetime.now()
            await router.generate([{"role": "user", "content": "ping"}], task_type="fast")
            latency = (datetime.now() - start).total_seconds()
            logger.info(f"LLM Gateway Latency: {latency:.2f}s")
        except Exception as e:
            logger.warning(f"⚠️ Health Check Warning: LLM Gateway sluggish or offline: {e}")

    async def task_auto_audit(self):
        """Randomly audits recent responses for security/quality."""
        logger.info("🛡️ Task: Random Auto-Audit...")
        # In a real scenario, we'd fetch a random recently saved response from Redis/DB
        # For now, it's a placeholder for the logic
        pass

    async def task_infra_drift_check(self):
        """
        Monitors core Docker containers and restarts them if they are down.
        Targets: litellm, qdrant, redis, infinity, postgres-iara
        """
        logger.info("🚜 Task: Infra Drift Check (Docker Socket)...")
        
        containers = ["litellm", "qdrant", "redis", "infinity", "postgres-iara"]
        socket_path = "/var/run/docker.sock"
        
        if not os.path.exists(socket_path):
            logger.warning(f"⚠️ Docker socket not found at {socket_path}. Skipping drift check.")
            return

        for container in containers:
            try:
                # We use curl against the unix socket for a zero-dep health check
                # Requirements: curl must be installed in the environment
                cmd = [
                    "curl", "--unix-socket", socket_path,
                    f"http://localhost/v1.41/containers/{container}/json"
                ]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.error(f"❌ Failed to query Docker socket for {container}: {stderr.decode()}")
                    continue
                
                info = json.loads(stdout.decode())
                state = info.get("State", {})
                status = state.get("Status", "unknown")
                
                if status != "running":
                    logger.warning(f"🚨 Container {container} is {status}. Attempting restart...")
                    restart_cmd = [
                        "curl", "-X", "POST", "--unix-socket", socket_path,
                        f"http://localhost/v1.41/containers/{container}/restart"
                    ]
                    r_process = await asyncio.create_subprocess_exec(*restart_cmd)
                    await r_process.wait()
                    
                    # Confirm Recovery
                    await asyncio.sleep(5)
                    confirm_process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await confirm_process.communicate()
                    info = json.loads(stdout.decode())
                    if info.get("State", {}).get("Status") == "running":
                        logger.info(f"✅ Container {container} confirmed running after restart.")
                    else:
                        logger.error(f"❌ Container {container} FAILED to recover after restart.")
                else:
                    logger.debug(f"🟢 Container {container} is healthy (running).")
                    
            except Exception as e:
                logger.error(f"⚠️ Error checking drift for {container}: {e}")

# Global instance
scheduler = AutonomousScheduler()

async def start():
    await scheduler.start()

async def stop():
    await scheduler.stop()
