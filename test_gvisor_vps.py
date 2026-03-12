import asyncio
import logging
from sandbox import execute_python

logging.basicConfig(level=logging.INFO)

async def verify_sandbox():
    print("🚀 Iniciando verificação do Sandbox gVisor...")
    
    # Teste 1: Execução básica e Kernel Release (gVisor costuma retornar algo diferente do Host)
    code_basic = "import os; print(f'Kernel Release: {os.uname().release}')"
    print("\n[Teste 1] Executando código básico...")
    res1 = await execute_python(code_basic)
    print(f"Resultado: {res1}")
    
    # Teste 2: Bloqueio de Rede (deve falhar ou retornar erro se tentar socket)
    code_net = "import socket; s = socket.socket(); s.settimeout(1); s.connect(('8.8.8.8', 53))"
    print("\n[Teste 2] Verificando bloqueio de rede...")
    res2 = await execute_python(code_net)
    print(f"Resultado (stderr deve conter erro de rede): {res2['stderr']}")

    # Teste 3: Read-only Filesystem
    code_fs = "with open('/etc/test.txt', 'w') as f: f.write('hack')"
    print("\n[Teste 3] Verificando filesystem read-only...")
    res3 = await execute_python(code_fs)
    print(f"Resultado (stderr deve conter Read-only file system): {res3['stderr']}")

if __name__ == "__main__":
    asyncio.run(verify_sandbox())
