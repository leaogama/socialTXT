import os
import re
import uuid
import logging
import glob
import httpx

from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from faster_whisper import WhisperModel
from playwright.sync_api import sync_playwright

# Instância global do modelo Whisper para não recarregar a cada requisição
_whisper_model = None
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "tiny")

# --- Configuração de Proxy Residencial ---
PROXY_URL = os.getenv("PROXY_URL", "").strip()

def get_proxy_config() -> dict:
    """Retorna configurações de proxy nos formatos usados por cada lib."""
    if not PROXY_URL:
        return {'url': '', 'requests': {}, 'playwright': {}, 'configured': False}
    
    return {
        'url': PROXY_URL,
        'requests': {'http://': PROXY_URL, 'https://': PROXY_URL},
        'playwright': {'server': PROXY_URL},
        'configured': True
    }

# --- Configuração de Browser Profile Persistente ---
USE_BROWSER_PROFILE = os.getenv("USE_BROWSER_PROFILE", "false").lower() == "true"
BROWSER_PROFILE_PATH = os.getenv("BROWSER_PROFILE_PATH", "/app/data/browser-profile")
ENABLE_VNC_BROWSER = os.getenv("ENABLE_VNC_BROWSER", "false").lower() == "true"

def get_browser_profile_status() -> dict:
    """Verifica o status do profile de navegador e sessão do YouTube."""
    import datetime
    
    if ENABLE_VNC_BROWSER:
        exists = os.path.exists("/app/vnc-profile")
        return {
            "vnc_mode": True,
            "enabled": True,
            "profile_path": "/app/vnc-profile",
            "profile_exists": exists,
            "youtube_session": {"detected": exists, "cookie_count": 0, "last_check": datetime.datetime.now().isoformat() if exists else ""}
        }
        
    if not USE_BROWSER_PROFILE:
        return {
            "vnc_mode": False,
            "enabled": False,
            "profile_path": BROWSER_PROFILE_PATH,
            "profile_exists": False,
            "youtube_session": {"detected": False, "cookie_count": 0, "last_check": ""}
        }
    
    exists = os.path.exists(BROWSER_PROFILE_PATH)
    
    # Faz uma verificação rápida de sessão se o diretório existir
    session_detected = False
    cookie_count = 0
    if exists:
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    BROWSER_PROFILE_PATH,
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
                )
                cookies = context.cookies("https://www.youtube.com")
                cookie_count = len(cookies)
                # Verifica se existem cookies comuns de auth do Google/YouTube
                if any(c['name'] in ['SID', 'SSID', 'LOGIN_INFO'] for c in cookies):
                    session_detected = True
                context.close()
        except Exception as e:
            logging.error(f"Erro ao verificar sessão do youtube: {e}")
            
    now = datetime.datetime.now().isoformat()
    return {
        "vnc_mode": False,
        "enabled": True,
        "profile_path": BROWSER_PROFILE_PATH,
        "profile_exists": exists,
        "youtube_session": {
            "detected": session_detected,
            "cookie_count": cookie_count,
            "last_check": now if exists else ""
        }
    }

def export_cookies_from_profile(logs: list) -> str:
    """Exporta cookies do browser profile persistente para um arquivo Netscape temporário."""
    if not USE_BROWSER_PROFILE or not os.path.exists(BROWSER_PROFILE_PATH):
        return ""
    
    try:
        logs.append("Exportando cookies do browser profile persistente...")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                BROWSER_PROFILE_PATH,
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
            )
            cookies = context.cookies()
            context.close()
            
        if not cookies:
            logs.append("Nenhum cookie encontrado no profile.")
            return ""
            
        # Converter para formato Netscape
        lines = ["# Netscape HTTP Cookie File"]
        for cookie in cookies:
            domain = cookie.get("domain", "")
            include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
            path = cookie.get("path", "/")
            is_secure = "TRUE" if cookie.get("secure", False) else "FALSE"
            expiry = str(int(cookie.get("expires", 0)))
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            lines.append(f"{domain}\t{include_subdomains}\t{path}\t{is_secure}\t{expiry}\t{name}\t{value}")
            
        cookie_path = f"/tmp/browser_cookies_{uuid.uuid4().hex[:8]}.txt"
        with open(cookie_path, "w") as f:
            f.write("\n".join(lines))
        logs.append(f"Cookies exportados com sucesso ({len(cookies)} cookies) para uso pelo yt-dlp.")
        return cookie_path
    except Exception as e:
        logs.append(f"Erro ao exportar cookies do profile: {e}")
        return ""

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logging.info(f"Carregando modelo Whisper ({WHISPER_MODEL_NAME})... Isso pode demorar na primeira vez.")
        # Usando cpu e int8 para economizar memória na VPS
        _whisper_model = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
    return _whisper_model

def parse_cookies_for_playwright(cookie_file: str) -> list:
    playwright_cookies = []
    if not os.path.exists(cookie_file):
        return playwright_cookies
    try:
        with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain = parts[0]
                    clean_domain = domain
                    if clean_domain.startswith('.'):
                        clean_domain = clean_domain[1:]
                    
                    # Filtra apenas domínios relevantes do google/youtube para evitar poluição no Playwright
                    if not any(d in clean_domain for d in ['youtube.com', 'google.com', 'google.com.br']):
                        continue
                        
                    name = parts[5]
                    value = parts[6]
                    path = parts[2]
                    secure = parts[3].upper() == 'TRUE'
                    try:
                        expires = int(parts[4])
                    except ValueError:
                        expires = -1
                        
                    cookie = {
                        'name': name,
                        'value': value,
                        'domain': clean_domain,
                        'path': path,
                        'secure': secure
                    }
                    if expires > 0:
                        cookie['expires'] = expires
                    playwright_cookies.append(cookie)
    except Exception as e:
        logging.error(f"Erro ao analisar cookies para Playwright: {e}")
    return playwright_cookies

def extract_youtube_id(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else ""

def extract_youtube_transcript_via_playwright(url: str, logs: list) -> str:
    logs.append("Tentando obter transcrição do YouTube via Playwright...")
    proxy_cfg = get_proxy_config()
    try:
        import html
        import xml.etree.ElementTree as ET
        
        with sync_playwright() as p:
            launch_args = {
                'headless': True,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            }
            if proxy_cfg['configured']:
                launch_args['proxy'] = proxy_cfg['playwright']
                logs.append(f"Playwright usando proxy residencial configurado.")
            
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            
            if USE_BROWSER_PROFILE:
                logs.append(f"Playwright usando perfil persistente em: {BROWSER_PROFILE_PATH}")
                launch_args['user_agent'] = user_agent
                context = p.chromium.launch_persistent_context(BROWSER_PROFILE_PATH, **launch_args)
            else:
                browser = p.chromium.launch(**launch_args)
                context = browser.new_context(user_agent=user_agent)
                
                # Tenta carregar cookies.txt fallback se profile estiver desligado
                data_dir = os.getenv("DATA_DIR", "/app/data")
                cookie_file = os.path.join(data_dir, "cookies.txt")
                if not os.path.exists(cookie_file):
                    cookie_file = "/app/cookies.txt"
                    
                if os.path.exists(cookie_file):
                    playwright_cookies = parse_cookies_for_playwright(cookie_file)
                    if playwright_cookies:
                        logs.append(f"Injetando {len(playwright_cookies)} cookies no navegador Playwright...")
                        context.add_cookies(playwright_cookies)
            
            page = context.new_page()
            logs.append("Playwright acessando página do YouTube...")
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            player_response = page.evaluate("() => window.ytInitialPlayerResponse")
            
            if USE_BROWSER_PROFILE:
                context.close()
            else:
                browser.close()
            
            if not player_response:
                logs.append("Objeto ytInitialPlayerResponse não encontrado no DOM do YouTube.")
                return ""
                
            captions = player_response.get("captions", {})
            tracklist = captions.get("playerCaptionsTracklistRenderer", {})
            caption_tracks = tracklist.get("captionTracks", [])
            
            if not caption_tracks:
                logs.append("Nenhuma faixa de legenda disponível no playerResponse do YouTube.")
                return ""
                
            logs.append(f"Encontradas {len(caption_tracks)} faixas de legenda no playerResponse.")
            # Escolhe o melhor idioma
            target_track = None
            for lang in ['pt', 'en', 'es']:
                for track in caption_tracks:
                    if track.get("languageCode", "").startswith(lang):
                        target_track = track
                        break
                if target_track:
                    break
            
            if not target_track:
                target_track = caption_tracks[0]
                
            lang_code = target_track.get("languageCode", "unknown")
            base_url = target_track.get("baseUrl")
            logs.append(f"Selecionada legenda no idioma: {lang_code}")
            
            if not base_url:
                logs.append("A faixa de legenda selecionada não possui baseUrl.")
                return ""
                
            logs.append("Baixando XML da legenda...")
            # Usa proxy também no download da legenda XML
            http_client_kwargs = {'timeout': 10.0}
            if proxy_cfg['configured']:
                http_client_kwargs['proxy'] = proxy_cfg['url']
            resp = httpx.get(base_url, **http_client_kwargs)
            resp.raise_for_status()
            
            root = ET.fromstring(resp.content)
            texts = []
            for elem in root.findall(".//text"):
                if elem.text:
                    texts.append(html.unescape(elem.text))
            
            logs.append(f"Legenda extraída com sucesso via Playwright ({len(texts)} segmentos).")
            return " ".join(texts)
            
    except Exception as e:
        logs.append(f"Extração Playwright do YouTube falhou: {str(e)}")
        return ""

def try_youtube_transcript_api(url: str, logs: list) -> str:
    video_id = extract_youtube_id(url)
    if not video_id:
        logs.append("Falha ao extrair ID do vídeo a partir da URL do YouTube.")
        return ""
    
    proxy_cfg = get_proxy_config()
    
    # Monta kwargs opcionais para o YouTubeTranscriptApi
    fetch_kwargs = {'languages': ['pt', 'en', 'es']}
    if proxy_cfg['configured']:
        # youtube-transcript-api aceita proxies no formato {"http": ..., "https": ...}
        fetch_kwargs['proxies'] = {
            'http': proxy_cfg['url'],
            'https': proxy_cfg['url'],
        }
        logs.append(f"youtube-transcript-api usando proxy residencial configurado.")
    else:
        logs.append("⚠ Nenhum proxy configurado (PROXY_URL). IPs de datacenter são bloqueados pelo YouTube.")
    
    # Tenta também com cookies se disponível
    data_dir = os.getenv("DATA_DIR", "/app/data")
    cookie_file = os.path.join(data_dir, "cookies.txt")
    if not os.path.exists(cookie_file):
        cookie_file = "/app/cookies.txt"
    if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 150:
        fetch_kwargs['cookies'] = cookie_file
        logs.append(f"youtube-transcript-api usando cookies de {cookie_file}.")
    
    try:
        logs.append("Tentando extrair transcrição nativa via youtube-transcript-api...")
        transcript_list = YouTubeTranscriptApi().fetch(video_id, **fetch_kwargs)
        logs.append("Sucesso! Transcrição obtida de forma nativa do YouTube.")
        return " ".join([t['text'] for t in transcript_list])
    except Exception as e:
        logs.append(f"youtube-transcript-api falhou: {str(e)}")
        
    return ""

def download_media_and_metadata_yt_dlp(url: str, output_base: str, logs: list, use_browser_cookies: bool = False) -> tuple[bool, str]:
    # Baixa apenas áudio e tenta extrair a legenda (descrição)
    ydl_opts = {
        'format': 'bestaudio/worst',
        'outtmpl': f'{output_base}.%(ext)s',
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'tv'],
            }
        },
        'remote_components': ['ejs:github'],
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'retries': 3,
        'file_access_retries': 3,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }
    
    # Configura proxy residencial se disponível
    proxy_cfg = get_proxy_config()
    if proxy_cfg['configured']:
        ydl_opts['proxy'] = proxy_cfg['url']
        logs.append(f"yt-dlp usando proxy residencial configurado.")
    else:
        logs.append("⚠ yt-dlp sem proxy configurado. Download pode falhar com 403 em IPs de datacenter.")
    
    cookie_temp_path = None
    if ENABLE_VNC_BROWSER:
        ydl_opts['cookiesfrombrowser'] = ('chrome', '/app/vnc-profile', None, None)
        logs.append(f"Injetando cookies diretamente do perfil VNC Chrome compartilhado.")
    elif use_browser_cookies and USE_BROWSER_PROFILE:
        cookie_temp_path = export_cookies_from_profile(logs)
        if cookie_temp_path:
            ydl_opts['cookiefile'] = cookie_temp_path
            logs.append(f"Injetando cookies exportados do profile no yt-dlp...")
    else:
        # Busca cookies na pasta de dados persistente (/app/data/cookies.txt) ou na raiz (/app/cookies.txt)
        data_dir = os.getenv("DATA_DIR", "/app/data")
        cookie_file = os.path.join(data_dir, "cookies.txt")
        if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 150:
            logs.append(f"Arquivo cookies.txt válido encontrado em {cookie_file}. Injetando cookies no yt-dlp...")
            ydl_opts['cookiefile'] = cookie_file
        elif os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 150:
            logs.append("Arquivo cookies.txt válido encontrado na raiz. Injetando cookies no yt-dlp...")
            ydl_opts['cookiefile'] = "cookies.txt"
        else:
            logs.append("Nenhum arquivo cookies.txt válido encontrado em /app/data/cookies.txt ou na raiz (usando requests sem cookies).")
        
    try:
        logs.append("Iniciando download e processamento de áudio via yt-dlp...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            description = info.get('description', '')
            logs.append("Download do áudio via yt-dlp concluído com sucesso.")
            return True, description
    except Exception as e:
        logs.append(f"yt-dlp falhou ao extrair áudio: {str(e)}")
        return False, ""
    finally:
        if cookie_temp_path and os.path.exists(cookie_temp_path):
            try:
                os.remove(cookie_temp_path)
            except:
                pass

def extract_with_playwright(url: str, output_base: str, logs: list) -> tuple[bool, str]:
    """Usa o Playwright (navegador real headless) para contornar bloqueios do Instagram e X"""
    description = ""
    try:
        logs.append("Iniciando Playwright (Chromium headless)...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
              )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            captured_media_urls = set()
            def handle_response(response):
                try:
                    if response.request.resource_type == "media" or ".mp4" in response.url:
                        if response.status in [200, 206]:
                            u = response.url
                            if u.startswith("//"):
                                u = "https:" + u
                            elif u.startswith("/"):
                                u = "https://www.instagram.com" + u
                            if not u.startswith("blob:"):
                                u = re.sub(r'&bytestart=\d+', '', u)
                                u = re.sub(r'&byteend=\d+', '', u)
                                captured_media_urls.add(u)
                except:
                    pass

            page.on("response", handle_response)
            
            logs.append(f"Playwright navegando até a URL: {url}")
            page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Tenta extrair legenda (og:description, etc)
            desc_element = page.locator('meta[property="og:description"]')
            if desc_element.count() > 0:
                description = desc_element.get_attribute("content") or ""
                logs.append(f"Legenda meta:og:description capturada com sucesso ({len(description)} chars).")
                
            # Busca ativamente vídeos no html como fallback extra
            videos = page.locator('video')
            logs.append(f"Tags de vídeo encontradas na página: {videos.count()}")
            for i in range(videos.count()):
                src = videos.nth(i).get_attribute("src")
                if src and not src.startswith("blob:"):
                    if src.startswith("//"): src = "https:" + src
                    src = re.sub(r'&bytestart=\d+', '', src)
                    src = re.sub(r'&byteend=\d+', '', src)
                    captured_media_urls.add(src)

            logs.append(f"Total de links de mídia capturados pelo Playwright: {len(captured_media_urls)}")
            # Tenta baixar as mídias capturadas e checa qual tem áudio
            import av
            success = False
            for media_url in captured_media_urls:
                try:
                    logs.append(f"Verificando integridade da mídia interceptada: {media_url[:80]}...")
                    resp = httpx.get(media_url, follow_redirects=True, timeout=15.0)
                    resp.raise_for_status()
                    
                    tmp_file = f"{output_base}_temp_{uuid.uuid4().hex[:4]}.mp4"
                    with open(tmp_file, "wb") as f:
                        f.write(resp.content)
                        
                    # Checa se o container de mídia tem áudio
                    has_audio = False
                    try:
                        with av.open(tmp_file, mode="r", metadata_errors="ignore") as container:
                            if len(container.streams.audio) > 0:
                                has_audio = True
                    except Exception as e:
                        logs.append(f"AV container erro: {str(e)}")
                        
                    if has_audio:
                        logs.append("Mídia válida com faixa de áudio encontrada!")
                        os.rename(tmp_file, f"{output_base}.mp4")
                        success = True
                        break
                    else:
                        logs.append("Mídia não possui faixa de áudio. Excluindo temporário...")
                        os.remove(tmp_file)
                except Exception as e:
                    logs.append(f"Falha ao baixar/verificar media: {str(e)}")

            browser.close()
            if success:
                return True, description
            else:
                logs.append("Playwright não encontrou nenhuma mídia de áudio válida para download.")
                return False, description
                
    except Exception as e:
        logs.append(f"Erro geral no fluxo do Playwright: {str(e)}")
        return False, description

def transcribe_audio(file_path: str, logs: list) -> str:
    try:
        logs.append("Carregando modelo Whisper para transcrição...")
        model = get_whisper_model()
        logs.append(f"Whisper carregado com sucesso. Transcrevendo {file_path}...")
        segments, _ = model.transcribe(file_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        logs.append(f"Transcrição concluída com sucesso ({len(text)} caracteres).")
        return text.strip()
    except Exception as e:
        logs.append(f"Erro ao transcrever áudio com Whisper: {str(e)}")
        return ""

def process_downloaded_audio(base_path: str, description: str, logs: list) -> str:
    """Extrai e processa áudios gerados pelo yt-dlp."""
    result_text = ""
    if description:
        result_text += f"Legenda/Descrição original:\n{description}\n\n"
        
    files = glob.glob(f"{base_path}*")
    logs.append(f"Arquivos de áudio prontos para transcrição local: {files}")
    for f in files:
        transcription = transcribe_audio(f, logs)
        if transcription:
            result_text += f"Transcrição do áudio:\n{transcription}"
        try:
            os.remove(f)
            logs.append(f"Limpeza concluída. Arquivo removido: {f}")
        except OSError as e:
            logs.append(f"Erro ao remover arquivo temporário {f}: {str(e)}")
            
    return result_text.strip()

def extract_social_content(url: str) -> tuple[str, list[str]]:
    debug_logs = []
    temp_id = str(uuid.uuid4())
    base_path = f"/tmp/{temp_id}"
    
    try:
        try:
            from core import VERSION
            debug_logs.append(f"Versão do App: {VERSION}")
        except Exception:
            debug_logs.append("Versão do App: Desconhecida")
            
        # --- PIPELINE DO YOUTUBE (5 Níveis) ---
        if "youtube.com" in url or "youtu.be" in url:
            debug_logs.append("Detectada URL do YouTube. Iniciando pipeline de extração de 5 níveis...")
            
            # Nível 1: youtube-transcript-api
            debug_logs.append("--- NÍVEL 1: youtube-transcript-api (Nativo) ---")
            text = try_youtube_transcript_api(url, debug_logs)
            if text: return f"Transcrição do YouTube: {text}", debug_logs
                
            # Nível 2: yt-dlp sem cookies do perfil
            debug_logs.append("--- NÍVEL 2: yt-dlp sem cookies persistentes ---")
            success, description = download_media_and_metadata_yt_dlp(url, base_path, debug_logs, use_browser_cookies=False)
            if success:
                return process_downloaded_audio(base_path, description, debug_logs), debug_logs
                
            # Nível 3: yt-dlp com cookies exportados do perfil persistente
            debug_logs.append("--- NÍVEL 3: yt-dlp com cookies do perfil persistente ---")
            if USE_BROWSER_PROFILE:
                success, description = download_media_and_metadata_yt_dlp(url, base_path, debug_logs, use_browser_cookies=True)
                if success:
                    return process_downloaded_audio(base_path, description, debug_logs), debug_logs
            else:
                debug_logs.append("PULADO: USE_BROWSER_PROFILE está false.")
                
            # Nível 4: Playwright (Perfil Persistente)
            debug_logs.append("--- NÍVEL 4: Extração via Playwright (Navegação Headless) ---")
            text = extract_youtube_transcript_via_playwright(url, debug_logs)
            if text: return f"Transcrição do YouTube: {text}", debug_logs
                
            # Nível 5: Falha
            debug_logs.append("--- NÍVEL 5: Falha Total ---")
            debug_logs.append("Todas as tentativas de extração do YouTube falharam.")
            return "", debug_logs


        # --- OUTRAS REDES (Instagram, TikTok, X) ---
        success = False
        description = ""

        # Instagram: tenta Playwright primeiro (navegador real)
        if "instagram.com" in url:
            debug_logs.append("Detectada URL do Instagram. Iniciando fluxo com Playwright...")
            success, description = extract_with_playwright(url, base_path, debug_logs)
        
        # Fallback: Baixar áudio + Descrição com yt-dlp
        if not success:
            debug_logs.append("Iniciando extração via download com yt-dlp + transcrição Whisper...")
            success, description = download_media_and_metadata_yt_dlp(url, base_path, debug_logs, use_browser_cookies=False)
        
        result_text = ""
        if success:
            result_text = process_downloaded_audio(base_path, description, debug_logs)
        elif description:
            result_text = f"Legenda/Descrição original:\n{description}\n\n"

        return result_text.strip(), debug_logs
        
    finally:
        # Garante a limpeza de QUALQUER arquivo criado nesta execução específica,
        # mesmo se ocorrer um erro fatal ou timeout no meio do processo.
        try:
            leftovers = glob.glob(f"{base_path}*")
            for f in leftovers:
                os.remove(f)
                debug_logs.append(f"Limpeza Forçada (Finally): Arquivo removido: {f}")
        except Exception:
            pass
