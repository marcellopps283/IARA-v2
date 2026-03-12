import asyncio
import logging
from brain import process

logging.basicConfig(level=logging.INFO)

async def test_full_chain():
    print("🚀 Verificando Cadeia Completa: Brain -> REDCODER -> gVisor")
    
    # Simula uma requisição que ative o sandbox
    # "Calcule os primeiros 10 números de Fibonacci"
    text = "Calcule os primeiros 10 números de Fibonacci e me mostre o resultado."
    chat_id = 12345
    
    print(f"\n[Usuário]: {text}")
    response = await process(text, chat_id)
    
    print(f"\n[IARA]: {response}")
    
    if "✅ **REDCODER" in response or "Fibonacci" in response:
        print("\n✅ SUCESSO! A cadeia completa funcionou.")
    else:
        print("\n❌ FALHA: A resposta não parece ter vindo do REDCODER.")

if __name__ == "__main__":
    asyncio.run(test_full_chain())
