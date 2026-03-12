import asyncio
import logging
import sys

# Configure logging to see output
logging.basicConfig(level=logging.INFO, format="%(message)s")

import memory_manager

async def test_mem0_contradiction():
    print("\n--- 🧠 TESTE 1: MEM0 (Resolução de Contradições) ---")
    print("Salvando fato inicial...")
    await memory_manager.add_core_memory("Eu sou um desenvolvedor sênior em Ruby", user_id="test_user")
    
    print("Recuperando fatos...")
    res = await memory_manager.search_core_memory("Qual minha profissão?", user_id="test_user")
    print(f"Resultado 1:\n{res}")
    
    print("\nAdicionando contradição...")
    await memory_manager.add_core_memory("Eu não trabalho com tecnologia, na verdade sou chef de cozinha avançado", user_id="test_user")
    
    print("Recuperando fatos atualizados...")
    res2 = await memory_manager.search_core_memory("Qual minha área de atuação?", user_id="test_user")
    print(f"Resultado 2 (esperado: chef de cozinha):\n{res2}")

async def test_lightrag_graph():
    print("\n--- 🕸️ TESTE 2: LIGHTRAG (Grafo de Conhecimento) ---")
    texto_longo = (
        "O projeto IARA passou por uma grande refatoração na Fase 7. "
        "O LangGraph foi escolhido porque o brain.py original com if/elif ficava intratável. "
        "A IARA roda em uma VPS do Google Cloud e usa Docker. "
        "Para a memória, o Marcello decidiu usar o Mem0 para resolver conflitos de persona, "
        "e o LightRAG para indexar as reuniões técnicas."
    )
    print("Ingerindo documento denso...")
    await memory_manager.ingest_knowledge_graph(texto_longo)
    
    print("Consultando o Grafo (Global Mode)...")
    res_global = await memory_manager.search_knowledge_graph("Por que o Marcello escolheu o LangGraph na Fase 7?", mode="global")
    print(f"\nResposta Global:\n{res_global}")

async def main():
    import traceback
    try:
        await test_mem0_contradiction()
    except Exception as e:
        print(f"Erro no teste Mem0:")
        traceback.print_exc()
        
    try:
        await test_lightrag_graph()
    except Exception as e:
        print(f"Erro no teste LightRAG:")
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        # We need to run this in the container, but if ran locally:
        print("Aviso: Recomenda-se rodar este script DENTRO do container na VPS (docker compose exec iara-core python test_memory.py)")
    asyncio.run(main())
