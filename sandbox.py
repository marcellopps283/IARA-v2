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
import re
from llm_router import LLMRouter

logger = logging.getLogger("sandbox")
router = LLMRouter()

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


def _strip_markdown(text: str) -> str:
    """Remove ```python and ``` blocks from LLM response."""
    text = re.sub(r"```python\n?", "", text)
    text = re.sub(r"```\n?", "", text)
    return text.strip()


async def redcoder_loop(goal: str, initial_code: str = "", iterations: int = 3) -> dict:
    """
    REDCODER Pattern: Blue Team (Builder) -> Execute -> Red Team (Destroyer) -> Refine.
    """
    current_code = initial_code or ""
    history = []
    
    # Se não temos código inicial, o Blue Team gera
    if not current_code:
        logger.info("🔵 Blue Team gerando código inicial...")
        current_code = await router.generate(
            messages=[
                {"role": "system", "content": "Você é o Blue Team (Builder). Escreva APENAS o código Python puro para resolver o problema. Sem markdown, sem explicações."},
                {"role": "user", "content": f"Objetivo: {goal}"}
            ],
            task_type="code"
        )
        current_code = _strip_markdown(current_code)

    for i in range(iterations):
        logger.info(f"🔄 REDCODER ieração {i+1}/{iterations}...")
        
        # 1. Execução
        result = await execute_python(current_code)
        stdout, stderr, exit_code = result["stdout"], result["stderr"], result["exit_code"]
        
        # 2. Red Team Analysis (Destroyer)
        if exit_code != 0 or "Error" in stderr:
            logger.warning(f"🔴 Red Team analisando falha (Exit {exit_code})...")
            red_feedback = await router.generate(
                messages=[
                    {"role": "system", "content": "Você é o Red Team (QA/Destroyer). Analise o erro e dê instruções curtas de correção."},
                    {"role": "user", "content": f"Código:\n{current_code}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"}
                ],
                task_type="fast",
                force_provider="groq",
                force_model="llama-3.1-8b-instant" # Forçando modelo rápido e eficiente para debug
            )
            
            if "PASS" in red_feedback.upper()[:10]:
                logger.info("🟢 Red Team deu PASS inesperado, mas vamos aceitar.")
                result["iterations"] = i + 1
                return result

            # 3. Blue Team Refactor (Builder)
            logger.info("🔵 Blue Team refatorando código...")
            current_code = await router.generate(
                messages=[
                    {"role": "system", "content": "Você é o Blue Team (Builder). Corrija o código baseado no feedback do Red Team. Retorne APENAS o código puro."},
                    {"role": "user", "content": f"Objetivo: {goal}\n\nCódigo Atual:\n{current_code}\n\nFeedback Red Team:\n{red_feedback}"}
                ],
                task_type="code"
            )
            current_code = _strip_markdown(current_code)
            history.append({"iteration": i+1, "feedback": red_feedback, "fixed_code": current_code})
        else:
            # Sucesso aparente, mas vamos pedir um "double check" do Red Team se for a primeira vez
            logger.info("🟢 Execução com sucesso. Red Team validando lógica...")
            red_check = await router.generate(
                messages=[
                    {"role": "system", "content": "Você é o Red Team. Se o código estiver perfeito para o objetivo, responda 'PASS'. Caso contrário, aponte a falha lógica."},
                    {"role": "user", "content": f"Objetivo: {goal}\n\nCódigo:\n{current_code}\n\nSaída:\n{stdout}"}
                ],
                task_type="fast",
                force_provider="groq",
                force_model="llama-3.1-8b-instant"
            )
            
            if "PASS" in red_check.upper()[:10]:
                logger.info("🏆 REDCODER: Código validado!")
                result["iterations"] = i + 1
                return result
            else:
                logger.warning(f"🔴 Red Team encontrou falha lógica: {red_check[:100]}...")
                # Repete o loop com o feedback lógico
                current_code = await router.generate(
                    messages=[
                        {"role": "system", "content": "Você é o Blue Team. Refatore o código baseado na falha lógica apontada. Retorne APENAS o código puro."},
                        {"role": "user", "content": f"Objetivo: {goal}\n\nCódigo Atual:\n{current_code}\n\nFeedback Lógico:\n{red_check}"}
                    ],
                    task_type="code"
                )
                current_code = _strip_markdown(current_code)

    # Se atingiu o limite, retorna o último resultado
    result["iterations"] = iterations
    result["final_code"] = current_code
    return result
