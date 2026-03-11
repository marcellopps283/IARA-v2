import httpx
import json

"""
Skill: open_meteo
Description: Telemetria passiva via API gratuita (sem chaves) do Open-meteo para localização geográfica aproximada.
"""

def get_schema():
    return {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Get current weather and 7-day forecast for a given latitude and longitude using Open-Meteo (Free API).",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Geographical latitude (e.g., -23.5505 for Sao Paulo)."
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Geographical longitude (e.g., -46.6333 for Sao Paulo)."
                    }
                },
                "required": ["latitude", "longitude"]
            }
        }
    }

async def execute(kwargs):
    lat = kwargs.get("latitude")
    lon = kwargs.get("longitude")
    
    if lat is None or lon is None:
        return "Erro: 'latitude' e 'longitude' obrigatórios."

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            # Formata a string de output para economizar tokens
            summary = (
                f"🌡️ Weather at [{lat}, {lon}]:\n"
                f"Current Temp: {data['current']['temperature_2m']}C, Humidity: {data['current']['relative_humidity_2m']}%\n"
                f"Max Temp Today: {data['daily']['temperature_2m_max'][0]}C\n"
                f"Min Temp Today: {data['daily']['temperature_2m_min'][0]}C\n"
                f"Rain Probability: {data['daily']['precipitation_probability_max'][0]}%"
            )
            return summary
    except Exception as e:
        return f"Falha ao acessar Open-Meteo: {e}"
