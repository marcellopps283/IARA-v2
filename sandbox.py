"""
sandbox.py — Docker-based Code Sandbox for IARA
Executes Python code in isolated containers on the VPS.
Replaces E2B cloud sandbox — free and unlimited.
"""

import asyncio
import logging
import uuid

logger = logging.getLogger("sandbox")

DOCKER_IMAGE = "python:3.12-slim"
TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 4000


async def execute_python(code: str) -> str:
    """
    Execute Python code in an isolated Docker container.
    Returns stdout/stderr output.
    """
    container_name = f"iara-sandbox-{uuid.uuid4().hex[:8]}"

    try:
        # Run code in a disposable container with no network and memory limits
        proc = await asyncio.create_subprocess_exec(
            "docker", "run",
            "--rm",                          # Auto-remove when done
            "--name", container_name,
            "--network", "none",             # No network (security)
            "--memory", "256m",              # Max 256MB RAM
            "--cpus", "0.5",                 # Max half a CPU
            "--read-only",                   # Read-only filesystem
            "--tmpfs", "/tmp:size=64m",      # Temp writable space
            DOCKER_IMAGE,
            "python", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            # Kill the container if it times out
            kill_proc = await asyncio.create_subprocess_exec(
                "docker", "kill", container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await kill_proc.wait()
            return f"⏱️ Timeout: código excedeu {TIMEOUT_SECONDS}s e foi terminado."

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += "\n[STDERR]\n" + stderr.decode("utf-8", errors="replace")

        output = output.strip()
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + f"\n\n[... truncado, {len(output)} chars total]"

        return output or "[Sem output]"

    except Exception as e:
        logger.error(f"❌ Sandbox error: {e}")
        return f"❌ Erro na sandbox: {e}"
