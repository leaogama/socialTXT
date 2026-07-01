import logging
from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel
import httpx

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from core import validate_env, get_transcript_text, summarize_with_llm

# Configura logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Cria app FastAPI
app = FastAPI(title="Social Summary API")

# Permite chamadas do mesmo domínio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SummarizeRequest(BaseModel):
    url: str
    detail: Literal["curto", "normal", "detalhado"] = "normal"
    language: str = "pt-BR"
    api_key: Optional[str] = None
    model: Optional[str] = None
    api_url: Optional[str] = None
    prompt_override: Optional[str] = None
    include_json_requirement: Optional[bool] = True

@app.post("/api/summarize")
async def api_summarize(request: SummarizeRequest):
    try:
        validate_env(request.api_key)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        logging.info("Recebendo URL via Web API: %s", request.url)
        transcript_text = await get_transcript_text(request.url)

        if not transcript_text:
            return {
                "url": request.url,
                "summary": "",
                "key_points": [],
                "possible_title": "",
                "content_type": "outro",
                "warnings": ["Não foi possível extrair texto/transcrição desta URL."]
            }

        summary = await summarize_with_llm(
            url=request.url,
            transcript_text=transcript_text,
            detail=request.detail,
            language=request.language,
            api_key_override=request.api_key,
            model_override=request.model,
            api_url_override=request.api_url,
            prompt_override=request.prompt_override,
            include_json_requirement=request.include_json_requirement
        )

        return {
            "url": request.url,
            "transcript_preview": transcript_text[:1200],
            "summary": summary.get("summary", ""),
            "key_points": summary.get("key_points", []),
            "possible_title": summary.get("possible_title", ""),
            "content_type": summary.get("content_type", "outro"),
            "warnings": summary.get("warnings", [])
        }

    except httpx.HTTPStatusError as error:
        logging.exception("Erro HTTP ao processar URL.")
        raise HTTPException(status_code=error.response.status_code, detail=f"Erro na API externa: {error.response.text[:200]}")
    except Exception as error:
        logging.exception("Erro inesperado.")
        raise HTTPException(status_code=500, detail=str(error))

# Serve the static files under /static but also route the root to index.html
import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")
