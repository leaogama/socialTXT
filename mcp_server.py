import os
import httpx
from mcp.server.fastmcp import FastMCP

# Inicializa o FastMCP
mcp = FastMCP("SocialTXT")

# URL base da API do SocialTXT (padrão é localhost, mas pode ser configurada via variável de ambiente)
API_BASE_URL = os.getenv("SOCIALTXT_API_URL", "http://localhost:8001").rstrip("/")
APP_USERNAME = os.getenv("APP_USERNAME", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

@mcp.tool()
async def summarize_social_url(
    url: str,
    detail: str = "normal",
    language: str = "pt-BR"
) -> str:
    """
    Extrai e resume o conteúdo de um link de rede social (YouTube, TikTok, Instagram Reels ou X/Twitter).
    Esta ferramenta envia a requisição para a API centralizada do SocialTXT.
    
    Args:
        url: URL completa do vídeo ou postagem.
        detail: Nível de detalhe do resumo ('curto', 'normal', 'detalhado'). Padrão é 'normal'.
        language: Idioma de resposta (ex: 'pt-BR', 'en', 'es'). Padrão é 'pt-BR'.
    """
    api_url = f"{API_BASE_URL}/api/summarize"
    
    payload = {
        "url": url,
        "detail": detail,
        "language": language
    }
    
    auth = (APP_USERNAME, APP_PASSWORD) if APP_USERNAME and APP_PASSWORD else None
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(api_url, json=payload, auth=auth)
            
            if response.status_code != 200:
                return f"Erro na API ({response.status_code}): {response.text}"
                
            data = response.json()
            
            # Formata o resultado de forma elegante em Markdown para a IA
            title = data.get("possible_title", "Resumo do Conteúdo")
            content_type = data.get("content_type", "outro")
            summary_desc = data.get("summary", "")
            key_points = data.get("key_points", [])
            warnings = data.get("warnings", [])

            output = []
            output.append(f"# {title}")
            output.append(f"**Tipo de Conteúdo:** {content_type.capitalize()}\n")
            
            if warnings:
                output.append("⚠️ **Alertas:**")
                for w in warnings:
                    output.append(f"- {w}")
                output.append("")

            output.append("## Resumo Geral")
            output.append(summary_desc)
            output.append("")

            if key_points:
                output.append("## Pontos Principais")
                for pt in key_points:
                    output.append(f"- {pt}")
                output.append("")

            return "\n".join(output).strip()

    except httpx.ConnectError:
        return (
            f"Erro de Conexão: Não foi possível alcançar a API do SocialTXT em {API_BASE_URL}.\n"
            f"Certifique-se de que o servidor web FastAPI (web.py) está ativo e rodando."
        )
    except Exception as e:
        return f"Erro ao processar resumo via API: {str(e)}"

if __name__ == "__main__":
    mcp.run()
