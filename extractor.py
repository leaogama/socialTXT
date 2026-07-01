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

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logging.info("Carregando modelo Whisper (small)... Isso pode demorar na primeira vez.")
        # Usando cpu e int8 para economizar memória na VPS
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model

def extract_youtube_id(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else ""

def try_youtube_transcript_api(url: str) -> str:
    video_id = extract_youtube_id(url)
    if not video_id:
        return ""
    try:
        logging.info("Tentando youtube-transcript-api...")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en', 'es'])
        return " ".join([t['text'] for t in transcript_list])
    except Exception as e:
        logging.warning("youtube-transcript-api falhou: %s", e)
        return ""

def download_media_and_metadata_yt_dlp(url: str, output_base: str) -> tuple[bool, str]:
    # Baixa apenas áudio e tenta extrair a legenda (descrição)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_base}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
        'no_warnings': True
    }
    
    # Injetando cookies se o arquivo existir e não for vazio
    cookie_file = "cookies.txt"
    if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 150:
        logging.info("Arquivo cookies.txt válido encontrado. Injetando no yt-dlp...")
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            description = info.get('description', '')
            return True, description
    except Exception as e:
        logging.error("yt-dlp falhou: %s", e)
        return False, ""

def extract_with_playwright(url: str, output_base: str) -> tuple[bool, str]:
    """Usa o Playwright (navegador real headless) para contornar bloqueios do Instagram e X"""
    description = ""
    try:
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
            
            logging.info("Playwright acessando a página: %s", url)
            page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Tenta extrair legenda (og:description, etc)
            desc_element = page.locator('meta[property="og:description"]')
            if desc_element.count() > 0:
                description = desc_element.get_attribute("content") or ""
                
            # Busca ativamente vídeos no html como fallback extra
            videos = page.locator('video')
            for i in range(videos.count()):
                src = videos.nth(i).get_attribute("src")
                if src and not src.startswith("blob:"):
                    if src.startswith("//"): src = "https:" + src
                    src = re.sub(r'&bytestart=\d+', '', src)
                    src = re.sub(r'&byteend=\d+', '', src)
                    captured_media_urls.add(src)

            # Tenta baixar as mídias capturadas e checa qual tem áudio
            import av
            success = False
            for media_url in captured_media_urls:
                try:
                    logging.info("Verificando mídia interceptada: %s...", media_url[:80])
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
                        pass
                        
                    if has_audio:
                        logging.info("Mídia válida com áudio encontrada!")
                        os.rename(tmp_file, f"{output_base}.mp4")
                        success = True
                        break
                    else:
                        os.remove(tmp_file)
                except Exception as e:
                    logging.warning("Falha ao baixar/verificar media: %s", e)

            if success:
                browser.close()
                return True, description
            else:
                logging.warning("Playwright não encontrou nenhuma mídia com áudio.")
                browser.close()
                return False, description
                
    except Exception as e:
        logging.error("Erro no Playwright: %s", e)
        return False, description

def transcribe_audio(file_path: str) -> str:
    try:
        model = get_whisper_model()
        logging.info(f"Iniciando transcrição com Whisper para o arquivo {file_path}...")
        segments, _ = model.transcribe(file_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text.strip()
    except Exception as e:
        logging.error("Erro ao transcrever áudio (talvez mídia corrompida): %s", e)
        return ""

def extract_social_content(url: str) -> str:
    result_text = ""
    
    # 1. Tentar nativo do YouTube primeiro
    if "youtube.com" in url or "youtu.be" in url:
        text = try_youtube_transcript_api(url)
        if text:
            return f"Transcrição do YouTube: {text}"

    temp_id = str(uuid.uuid4())
    base_path = f"/tmp/{temp_id}"

    success = False
    description = ""

    # 2. Instagram: tenta Playwright primeiro (navegador real)
    if "instagram.com" in url:
        logging.info("Iniciando Playwright para burlar bloqueio do Instagram...")
        success, description = extract_with_playwright(url, base_path)
    
    # 3. Fallback: Baixar áudio + Descrição com yt-dlp (com suporte a cookies opcional)
    if not success:
        logging.info("Iniciando yt-dlp para tentar extrair mídia...")
        success, description = download_media_and_metadata_yt_dlp(url, base_path)
    
    if description:
        result_text += f"Legenda/Descrição original:\n{description}\n\n"

    if success:
        # Encontra o arquivo de mídia gerado (.mp4, .mp3, .m4a, etc) e transcreve
        files = glob.glob(f"{base_path}*")
        for f in files:
            transcription = transcribe_audio(f)
            if transcription:
                result_text += f"Transcrição do áudio:\n{transcription}"
            # Limpeza
            try:
                os.remove(f)
            except OSError:
                pass

    return result_text.strip()
