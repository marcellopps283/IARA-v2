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
            "name": "get_system_status",
            "description": "Carrega as informações de Bateria, Memória RAM, Uso de CPU e Armazenamento do dispositivo Android em que a IARA roda.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Cria um alarme ou lembrete para a IARA avisar o usuário no futuro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "A mensagem do que o usuário deve ser lembrado."
                    },
                    "time_expression": {
                        "type": "string",
                        "description": "A indicação natural do tempo. Ex: 'daqui a 10 minutos', 'às 18:00', 'amanhã de manhã'."
                    }
                },
                "required": ["message", "time_expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_flashlight",
            "description": "Liga ou desliga a lanterna física do celular da IARA (apenas Android).",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Estado que a lanterna deve ficar."
                    }
                },
                "required": ["state"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_location",
            "description": "Lê o sensor físico de GPS e retorna a latitude, longitude e precisão da localização do celular.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Extrai e lê perfeitamente todo o conteúdo legível ou artigo de um link da internet (URL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Link completo que começa com http ou https."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_sandbox",
            "description": "Gera código Python pesado (como plot de gráficos, cálculos ML ou pandas) e roda em uma máquina virtual isolada na nuvem (E2B).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "O que você quer que o script em Python da nuvem faça e calcule para nós."
                    }
                },
                "required": ["task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "swarm_delegate",
            "description": "Delega uma tarefa para a frota de agentes que rodam em background em outros celulares da rede (Swarm Workers).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "A tarefa que o worker deve completar de forma autônoma."
                    },
                    "role": {
                        "type": "string",
                        "enum": ["pesquisador", "revisor"],
                        "description": "O estilo/papel que o worker escravo deve adotar."
                    }
                },
                "required": ["task", "role"]
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
