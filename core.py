import os
import json
import logging
import asyncio
from typing import Dict, Any

import httpx
from dotenv import load_dotenv

from extractor import extract_social_content

load_dotenv()

VERSION = "1.5.2"

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_URL = os.getenv(
    "LLM_API_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "deepseek/deepseek-chat-v3-0324"
)

DATA_DIR = os.getenv("DATA_DIR", "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

def get_backend_settings() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logging.exception("Erro ao ler arquivo de configurações backend.")
    return {}

def save_backend_settings(settings: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception("Erro ao salvar arquivo de configurações backend.")

def validate_env(api_key_override: str = None) -> None:
    if api_key_override:
        return
    settings = get_backend_settings()
    if settings.get("api_key"):
        return
    if LLM_API_KEY:
        return
    raise RuntimeError("Faltou configurar a chave de API da IA. Informe no painel de Configurações.")

async def get_transcript_text(url: str) -> tuple[str, list[str]]:
    """Roda a extração que é bloqueante (CPU/IO) de forma assíncrona usando threads"""
    return await asyncio.to_thread(extract_social_content, url)

async def summarize_with_llm(
    url: str,
    transcript_text: str,
    detail: str,
    language: str,
    api_key_override: str = None,
    model_override: str = None,
    api_url_override: str = None,
    prompt_override: str = None,
    include_json_requirement: bool = True
) -> Dict[str, Any]:
    
    settings = get_backend_settings()
    final_api_key = api_key_override or settings.get("api_key") or LLM_API_KEY
    final_model = model_override or settings.get("model") or LLM_MODEL
    final_api_url = api_url_override or settings.get("api_url") or LLM_API_URL
    
    base_prompt = prompt_override.strip() if prompt_override else (
        "Você é um analisador de conteúdo de redes sociais. "
        "Resuma o conteúdo com fidelidade, sem inventar informações. "
        "Quando a transcrição parecer incompleta, avise claramente."
    )
    
    json_requirement = (
        "\n\nRetorne sua resposta estritamente no formato JSON, contendo as chaves: "
        "'summary' (string), 'key_points' (lista de strings), 'possible_title' (string) "
        "e 'content_type' (string, como 'notícia', 'dica', 'humor', etc)."
    )
    
    system_prompt = base_prompt + (json_requirement if include_json_requirement else "")

    user_prompt = f"""
Analise o conteúdo abaixo.

URL:
{url}

Idioma da resposta:
{language}

Nível de detalhe:
{detail}

Transcrição/Legenda:
{transcript_text}

Responda exclusivamente em JSON válido neste formato:
{{
  "summary": "resumo principal",
  "key_points": ["ponto 1", "ponto 2", "ponto 3"],
  "possible_title": "título curto",
  "content_type": "reel/video/post/aula/notícia/opinião/outro",
  "warnings": ["alertas sobre limitações da transcrição, se houver"]
}}
""".strip()

    payload = {
        "model": final_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {final_api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(final_api_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]

    try:
        # Remover blocos markdown se a LLM responder com ```json ... ```
        clean_content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_content)
    except json.JSONDecodeError:
        logging.exception("A LLM não retornou JSON válido.")
        return {
            "summary": content,
            "key_points": [],
            "possible_title": "",
            "content_type": "outro",
            "warnings": [
                "A resposta da LLM não veio em JSON válido; retorno bruto preservado."
            ]
        }
