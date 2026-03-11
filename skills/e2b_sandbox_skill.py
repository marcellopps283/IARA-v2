import os
from e2b_code_interpreter import Sandbox

"""
Skill: e2b_sandbox
Description: Executa código Python complexo, Data Science, ou scripts perigosos na nuvem via E2B Code Interpreter.
"""

def get_schema():
    return {
        "type": "function",
        "function": {
            "name": "e2b_sandbox",
            "description": "Execute complex Python code (like Data Science, Pandas, Matplotlib) or high-risk scripts in an isolated ephemeral E2B Cloud Sandbox. Returns stdout, stderr and captures base64 images of plotted charts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute in the cloud sandbox."
                    }
                },
                "required": ["code"]
            }
        }
    }

async def execute(kwargs):
    code = kwargs.get("code")
    if not code:
        return "Erro: 'code' obrigatório."

    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        return "Erro: E2B_API_KEY não está configurada no .env."

    try:
        print("[E2B Cloud] Iniciando Sandbox Efêmera do Code Interpreter...")
        with Sandbox.create() as sandbox:
            execution = sandbox.run_code(code)
            
            output_msg = ""
            
            if execution.text:
                output_msg += f"stdout:\n{execution.text}\n"
                
            if execution.error:
                output_msg += f"stderr:\n{execution.error.name}: {execution.error.value}\n{execution.error.traceback}\n"
                
            # Extrair resultados visuais (gráfico plotado)
            if execution.results:
                for idx, result in enumerate(execution.results):
                    if result.png:
                        # Embutir a imagem convertida para markdown base64 tag
                        img_tag = f"![E2B Chart {idx}](data:image/png;base64,{result.png})"
                        output_msg += f"\nChart Gerado:\n{img_tag}\n"
                    elif result.text:
                        output_msg += f"\nResult {idx}:\n{result.text}\n"
                        
            if not output_msg:
                output_msg = "Execução concluída sem output visível."
                
            return output_msg

    except Exception as e:
        return f"Falha na E2B Sandbox: {e}"
