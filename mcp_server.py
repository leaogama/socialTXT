import os
import asyncio
from mcp.server.fastmcp import FastMCP
from core import get_transcript_text, summarize_with_llm, validate_env

# Inicializa o FastMCP
mcp = FastMCP("SocialTXT")

@mcp.tool()
async def summarize_social_url(
    url: str,
    detail: str = "normal",
    language: str = "pt-BR"
) -> str:
    """
    Extrai e resume o conteúdo de um link de rede social (YouTube, TikTok, Instagram Reels ou X/Twitter).
    
    Args:
        url: URL completa do vídeo ou postagem.
        detail: Nível de detalhe do resumo ('curto', 'normal', 'detalhado'). Padrão é 'normal'.
        language: Idioma de resposta (ex: 'Português (BR)', 'English'). Padrão é 'pt-BR'.
    """
    try:
        # Valida se a chave de API está disponível (no .env ou env vars)
        try:
            validate_env()
        except RuntimeError as e:
            return f"Erro de Configuração: {str(e)}\nCertifique-se de configurar a variável LLM_API_KEY no seu arquivo .env ou nas variáveis de ambiente do seu sistema."

        # Extrai transcrição
        transcript_text = await get_transcript_text(url)
        if not transcript_text:
            return "Erro: Não foi possível extrair nenhuma transcrição ou legenda deste link."

        # Roda a LLM
        summary = await summarize_with_llm(
            url=url,
            transcript_text=transcript_text,
            detail=detail,
            language=language
        )

        # Formata resultado legível
        title = summary.get("possible_title", "Sem título")
        content_type = summary.get("content_type", "outro")
        summary_desc = summary.get("summary", "")
        key_points = summary.get("key_points", [])
        warnings = summary.get("warnings", [])

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

    except Exception as e:
        return f"Erro ao processar resumo: {str(e)}"

if __name__ == "__main__":
    mcp.run()
