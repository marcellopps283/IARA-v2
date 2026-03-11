import os
import importlib.util
import inspect
import toml
from pydantic import BaseModel, Field
from typing import Dict, Any, List

SKILLS_DIR = os.path.dirname(__file__)

class SkillManifest(BaseModel):
    name: str
    description: str
    entrypoint: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)

def _build_groq_schema(manifest: SkillManifest) -> dict:
    return {
        "type": "function",
        "function": {
            "name": manifest.name,
            "description": manifest.description,
            "parameters": {
                "type": "object",
                "properties": manifest.parameters,
                "required": manifest.required
            }
        }
    }

def load_skills():
    """
    Varre a pasta skills/ e carrega os módulos dinamicamente.
    Suporta o antigo formato (.py) e o novo formato Declarativo (pastas c/ manifest.toml)
    """
    tools = []
    skill_functions = {}
    
    for item in os.listdir(SKILLS_DIR):
        item_path = os.path.join(SKILLS_DIR, item)
        
        # --- CARREGADOR DECLARATIVO (NOVO) ---
        if os.path.isdir(item_path):
            manifest_path = os.path.join(item_path, "manifest.toml")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        data = toml.load(f)
                        
                    # Validação Pydantic
                    manifest = SkillManifest(**data)
                    schema = _build_groq_schema(manifest)
                    
                    # Carrega o entrypoint Python indicado
                    py_file = os.path.join(item_path, manifest.entrypoint)
                    module_name = f"skill_{manifest.name}"
                    
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "execute"):
                        tools.append(schema)
                        skill_functions[manifest.name] = module.execute
                        print(f"📦 Skill Declarativa '{manifest.name}' carregada.")
                except Exception as e:
                    print(f"Erro ao carregar skill declarativa {item}: {e}")
                    
        # --- CARREGADOR LEGACY (.py) ---
        elif os.path.isfile(item_path) and item.endswith("_skill.py"):
            module_name = item[:-3]
            spec = importlib.util.spec_from_file_location(module_name, item_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "get_schema") and hasattr(module, "execute"):
                schema = module.get_schema()
                func_name = schema["function"]["name"]
                
                tools.append(schema)
                skill_functions[func_name] = module.execute
                
    return tools, skill_functions
