"""
sandbox.py — Docker-based Code Sandbox for IARA
Executes Python code in isolated containers on the VPS.
Replaces E2B cloud sandbox — free and unlimited.
"""

import asyncio
from asyncio import subprocess
import logging
import uuid
import os

logger = logging.getLogger("sandbox")

DOCKER_IMAGE = "python:3.12-slim"
TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 4000


async def execute_python(code: str) -> dict:
    """
    Execute Python code in an isolated gVisor container.
    Returns a dict with stdout, stderr, and exit_code.
    """
    container_name = f"iara-sandbox-{uuid.uuid4().hex[:8]}"
    
    # Security options for gVisor + Seccomp
    security_opts = [
        "--runtime", "runsc",                # gVisor isolation
        "--network", "none",                 # No network
        "--memory", "512m",                  # RAM limit
        "--cpus", "0.5",                     # CPU limit
        "--read-only",                       # RO Filesystem
        "--security-opt", "no-new-privileges:true",
        "--security-opt", "seccomp=./seccomp-sandbox.json",
        "--cap-drop", "ALL",                 # Drop all capabilities
        "--tmpfs", "/tmp:size=100m",         # Writable temp
    ]

    try:
        cmd = ["docker", "run", "--rm", "--name", container_name] + security_opts + [DOCKER_IMAGE, "python", "-c", code]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=TIMEOUT_SECONDS,
            )
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            # Kill the container if it times out
            kill_proc = await asyncio.create_subprocess_exec(
                "docker", "kill", container_name,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await kill_proc.wait()
            return {
                "stdout": "",
                "stderr": f"⏱️ Timeout: código excedeu {TIMEOUT_SECONDS}s e foi terminado.",
                "exit_code": 124
            }

        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        # Auto-truncate large outputs
        if len(stdout_str) > MAX_OUTPUT_CHARS:
            stdout_str = f"{stdout_str[:MAX_OUTPUT_CHARS]}\n\n[... truncado]"
        
        return {
            "stdout": stdout_str.strip(),
            "stderr": stderr_str.strip(),
            "exit_code": exit_code
        }

    except Exception as e:
        logger.error(f"❌ Sandbox error: {e}")
        return {
            "stdout": "",
            "stderr": f"❌ Erro na sandbox: {str(e)}",
            "exit_code": 1
        }


async def redcoder_loop(code: str, iterations: int = 3) -> dict:
    """
    REDCODER Pattern: Blue Team (Builder) -> Execute -> Red Team (Destroyer) -> Refine.
    Currently a placeholder for the iterative loop logic.
    """
    # TODO: Implement full REDCODER loop with LLM calls
    result = await execute_python(code)
    return result
