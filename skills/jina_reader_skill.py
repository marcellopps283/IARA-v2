import httpx

"""
Skill: jina_reader
Description: Coleta o texto puro (Markdown) de qualquer URL da internet usando a API gratuita Jina Reader, ignorando paywalls simples e anúncios.
"""

def get_schema():
    return {
        "type": "function",
        "function": {
            "name": "read_web_url_jina",
            "description": "Extract raw markdown text/content from any URL via Jina Reader. Bypasses simple paywalls and ads. Good for documentation and articles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The exact https:// URL to read/scrape."
                    }
                },
                "required": ["url"]
            }
        }
    }

async def execute(kwargs):
    url = kwargs.get("url")
    if not url:
        return "Erro: 'url' obrigatório."

    try:
        jina_url = f"https://r.jina.ai/{url}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(jina_url)
            response.raise_for_status()
            
            # Limita a 10.000 caracteres para evitar estourar Token da Kitty atoa
            content = response.text
            if len(content) > 10000:
                print("⚠️ [Jina Reader] Link imenso. Truncando para 10k chars.")
                return content[:10000] + "\n\n[TRUNCATED... Document is too long]"
            return content
    except Exception as e:
        return f"Falha na leitura via Jina Reader: {e}"
