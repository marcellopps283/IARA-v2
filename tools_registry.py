"""
tools_registry.py — Cadastro central de Tools (Function Calling)
Define os schemas no formato OpenAI nativo para injeção via LLMRouter.
"""

TOOLS_REGISTRY = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Realiza uma busca na internet para encontrar informações gerais ou notícias atualizadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Os termos da pesquisa para jogar no buscador."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": "Inicia um agente de pesquisa profunda e detalhada para análise acadêmica, técnica ou multi-fontes. Muito demorado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "O tema complexo ou assunto que precisa ser pesquisado a fundo."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Salva um fato permanente e muito importante sobre o usuário na memória central da IARA.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "A categoria da memória (ex: preferencia, regra, familiar, rotina)."
                    },
                    "content": {
                        "type": "string",
                        "description": "A declaração exata do fato para memorizar."
                    }
                },
                "required": ["category", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Lê a memória central e recupera tudo que a IARA sabe permanentemente sobre o usuário ou projeto.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Obtém as condições atuais de clima e temperatura na localização da IARA.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deep_research_council",
            "description": "Convoca o 'Conselho de Modelos'. Dispara a mesma pergunta com diferentes LLMs (Groq, Cerebras, Mistral) ao mesmo tempo para obter opiniões e debates de múltiplas IAs e tirar um veredito presidencial imparcial.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A pergunta polêmica, complexa ou filosófica as IAs devem debater."
                    }
                },
                "required": ["query"]
            }
        }
    }
]
