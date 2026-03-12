import asyncio
import logging
from sandbox import redcoder_loop

logging.basicConfig(level=logging.INFO)

async def test_redcoder():
    print("🚀 Verificando Loop REDCODER (Auto-Correção)...")
    
    # Objetivo: Fatorial de 5
    # Código inicial com ERRO proposital: 'resul' vs 'result'
    goal = "Calcular o fatorial de 5 e imprimir o resultado."
    buggy_code = "n = 5; result = 1; for i in range(1, n+1): resul *= i; print(result)"
    
    print(f"\n[Teste] Iniciando com código bugado: {buggy_code}")
    result = await redcoder_loop(goal, buggy_code, iterations=3)
    
    print("\n--- Resultado Final ---")
    print(f"Stdout: {result.get('stdout')}")
    print(f"Stderr: {result.get('stderr')}")
    print(f"Exit Code: {result.get('exit_code')}")
    print(f"Iterações: {result.get('iterations')}")
    
    if result.get('exit_code') == 0 and "120" in result.get('stdout'):
        print("\n✅ SUCESSO! O REDCODER corrigiu o bug e obteve o fatorial correto (120).")
    else:
        print("\n❌ FALHA: O REDCODER não conseguiu corrigir o bug.")

if __name__ == "__main__":
    asyncio.run(test_redcoder())
