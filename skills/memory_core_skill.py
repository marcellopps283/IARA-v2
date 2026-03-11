import os
import aiosqlite
from core import DB_NAME

"""
Skill: memory_core
Description: Permite que a Kitty insira notas permanentes na sua própria base de dados de memória.
"""

def get_schema():
    return {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save important user preferences or data permanently to DB to survive restarts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Information to persist."
                    }
                },
                "required": ["content"]
            }
        }
    }

async def execute(kwargs):
    content = kwargs.get("content")
    if not content:
        return "Erro: conteúdo vazio."
        
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO core_memory (content) VALUES (?)", (content,))
        await db.commit()
    return f"Memória '{content[:20]}...' salva com sucesso no Núcleo Permanente (Seguro contra deleção)."
