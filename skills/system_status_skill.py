import json
from core import get_status

"""
Skill: system_status
Description: Permite que a inteligência artificial acesse os dados de bateria e temperatura do hardware hospedeiro sob demanda.
"""

def get_schema():
    return {
        "type": "function",
        "function": {
            "name": "check_system_status",
            "description": "Read hardware sensors (Termux API) to get current battery and temperature of the Host (S21 Ultra).",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    }

async def execute(kwargs):
    # A função original do core.py retorna uma string JSON
    status_str = await get_status()
    return status_str
