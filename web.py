import logging
import secrets
import os
from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel
import httpx

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core import (
    validate_env,
    get_transcript_text,
    summarize_with_llm,
    get_backend_settings,
    save_backend_settings,
    VERSION
)

# Configura logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Cria app FastAPI
app = FastAPI(title="Social Summary API")

# Configuração de Autenticação Básica (Opcional - Ativa se APP_USERNAME/PASSWORD estiverem definidos)
security = HTTPBasic()
APP_USERNAME = os.getenv("APP_USERNAME", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    if not APP_USERNAME or not APP_PASSWORD:
        return ""
    
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = APP_USERNAME.encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = APP_PASSWORD.encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=401,
            detail="Credenciais de acesso inválidas.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

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

class SettingsModel(BaseModel):
    api_key: Optional[str] = ""
    model: Optional[str] = ""
    api_url: Optional[str] = ""

@app.get("/api/settings")
def get_settings(username: str = Depends(verify_credentials)):
    settings = get_backend_settings()
    raw_key = settings.get("api_key", "")
    masked_key = ""
    if raw_key:
        if len(raw_key) > 8:
            masked_key = f"{raw_key[:4]}...{raw_key[-4:]}"
        else:
            masked_key = "••••••••"
    return {
        "api_key": masked_key,
        "model": settings.get("model", ""),
        "api_url": settings.get("api_url", "")
    }

@app.post("/api/settings")
def post_settings(settings: SettingsModel, username: str = Depends(verify_credentials)):
    try:
        current = get_backend_settings()
        new_key = settings.api_key
        # Se vier mascarada do front (contendo ... ou •), mantém a chave atual
        if new_key and ("..." in new_key or "•" in new_key or "·" in new_key):
            new_key = current.get("api_key", "")
        
        save_backend_settings({
            "api_key": new_key,
            "model": settings.model,
            "api_url": settings.api_url
        })
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/summarize")
async def api_summarize(request: SummarizeRequest, username: str = Depends(verify_credentials)):
    try:
        validate_env(request.api_key)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        logging.info("Recebendo URL via Web API: %s", request.url)
        transcript_text, debug_logs = await get_transcript_text(request.url)

        if not transcript_text:
            warnings = ["Não foi possível extrair texto/transcrição desta URL."]
            if debug_logs:
                warnings.append("--- DETALHES DO PIPELINE DE EXTRAÇÃO (DEBUG) ---")
                for log in debug_logs:
                    warnings.append(f"• {log}")
            return {
                "url": request.url,
                "summary": "",
                "key_points": [],
                "possible_title": "",
                "content_type": "outro",
                "warnings": warnings
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

@app.get("/api/version")
def get_version():
    return {"version": VERSION}

@app.get("/api/proxy_status")
def get_proxy_status(username: str = Depends(verify_credentials)):
    proxy_url = os.getenv("PROXY_URL", "").strip()
    if not proxy_url:
        return {"configured": False, "protocol": ""}
    
    # Detecta protocolo sem expor a URL completa
    protocol = "http"
    if proxy_url.startswith("socks5"):
        protocol = "socks5"
    elif proxy_url.startswith("socks4"):
        protocol = "socks4"
    elif proxy_url.startswith("https"):
        protocol = "https"
    
    return {"configured": True, "protocol": protocol}

@app.post("/api/upload_cookies")
async def upload_cookies(file: UploadFile = File(...), username: str = Depends(verify_credentials)):
    if not file.filename.endswith(".txt") and not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser .txt ou .json")
    
    data_dir = os.getenv("DATA_DIR", "/app/data")
    os.makedirs(data_dir, exist_ok=True)
    cookie_path = os.path.join(data_dir, "cookies.txt")
    
    try:
        content = await file.read()
        with open(cookie_path, "wb") as f:
            f.write(content)
        return {"status": "success", "message": "Cookies atualizados com sucesso"}
    except Exception as e:
        logging.exception("Erro ao salvar cookies.")
        raise HTTPException(status_code=500, detail=str(e))

# Serve the static files under /static but also route the root to index.html
import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root(username: str = Depends(verify_credentials)):
    with open("static/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Injeta a versão dinâmica no HTML para cache-busting automático
    content = content.replace("?v=APP_VERSION", f"?v={VERSION}")
    
    return HTMLResponse(content=content)
