"""
scheduler.py — IARA Background Autonomous Scheduler (Phase 14)
Handles proactive tasks like memory refinement, auto-audits, and system health checks.
"""

import asyncio
import logging
import json
from datetime import datetime
import importlib

import core
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
        
        # Ensure database is ready
        await core.init_db()
        
        # Start the main loop
        asyncio.create_task(self._main_loop())

    async def stop(self):
        """Stops the scheduler."""
        self.running = False
        logger.info("🛑 IARA Background Scheduler Stopped")

    async def _main_loop(self):
        """Main loop that checks for pending jobs every minute."""
        while self.running:
            try:
                # 1. Memory Refinement (Consolidação)
                await self.task_memory_refinement()
                
                # 2. System Health Check
                await self.task_health_check()
                
                # 3. Random Auto-Audit
                await self.task_auto_audit()
                
            except Exception as e:
                logger.error(f"❌ Scheduler loop error: {e}", exc_info=True)
            
            # Wait for 1 hour (or adjusted interval)
            # For now, let's keep it at 1 hour for background maintenance
            await asyncio.sleep(3600)

    async def task_memory_refinement(self):
        """
        Consolidates episodic memory into the knowledge graph and core memory.
        """
        logger.info("🧠 Task: Memory Refinement...")
        # Get unprocessed episodes (logic based on core.py)
        episodes = await core.get_unprocessed_episodes(limit=10)
        if not episodes:
            logger.debug("Checked: No new episodes to refine.")
            return

        for ep in episodes:
            text = ep["summary"]
            # Ingest into Knowledge Graph (LightRAG)
            await memory_manager.ingest_knowledge_graph(text)
            logger.debug(f"Ingested episode {ep['id']} into Knowledge Graph.")
            
        # For now, we don't delete them to avoid data loss, 
        # but in a production setup, we'd mark them as 'processed'.
        logger.info(f"✅ Refined {len(episodes)} memory episodes.")

    async def task_health_check(self):
        """Checks latency and status of key components."""
        logger.info("🌡️ Task: System Health Check...")
        # Check LLM Gateway
        router = brain.get_router()
        try:
            start = datetime.now()
            await router.generate([{"role": "user", "content": "ping"}], task_type="chat_fast")
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

# Global instance
scheduler = AutonomousScheduler()

async def start():
    await scheduler.start()

async def stop():
    await scheduler.stop()
