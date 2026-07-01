import logging
from typing import Literal, Dict, Any
import httpx

from mcp.server.fastmcp import FastMCP
from core import validate_env, get_transcript_text, summarize_with_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

mcp = FastMCP("Social Summary MCP")

@mcp.tool()
async def summarize_social_link(
    url: str,
    detail: Literal["curto", "normal", "detalhado"] = "normal",
    language: str = "pt-BR"
) -> Dict[str, Any]:
    """
    Recebe um link de rede social e retorna um resumo do conteúdo.
    """
    try:
        validate_env()
        logging.info("Recebendo URL para resumo via MCP: %s", url)

        transcript_text = await get_transcript_text(url)

        if not transcript_text:
            return {
                "url": url,
                "summary": "",
                "key_points": [],
                "possible_title": "",
                "content_type": "outro",
                "warnings": ["Não foi possível extrair texto/transcrição desta URL."]
            }

        summary = await summarize_with_llm(
            url=url,
            transcript_text=transcript_text,
            detail=detail,
            language=language
        )

        return {
            "url": url,
            "transcript_preview": transcript_text[:1200],
            "summary": summary.get("summary", ""),
            "key_points": summary.get("key_points", []),
            "possible_title": summary.get("possible_title", ""),
            "content_type": summary.get("content_type", "outro"),
            "warnings": summary.get("warnings", [])
        }

    except httpx.HTTPStatusError as error:
        logging.exception("Erro HTTP ao processar URL via MCP.")
        return {
            "url": url,
            "summary": "",
            "key_points": [],
            "warnings": [f"Erro HTTP: {error.response.status_code}", error.response.text[:500]]
        }
    except Exception as error:
        logging.exception("Erro inesperado ao processar URL via MCP.")
        return {
            "url": url,
            "summary": "",
            "key_points": [],
            "warnings": [f"Erro inesperado: {str(error)}"]
        }

if __name__ == "__main__":
    mcp.run()
