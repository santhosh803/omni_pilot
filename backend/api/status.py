"""System status endpoint — reports which backend services are available.

Returns a structured JSON response listing each service and its status:
  - ok        — service is configured and reachable
  - degraded  — service is configured but not responding (or using fallback)
  - offline   — service is not configured

The frontend uses this to display degradation indicators (Item 9).
"""

import os

import httpx
from fastapi import APIRouter

from backend.middleware.auth import is_auth_enabled

router = APIRouter(prefix="/status", tags=["Status"])


def _check_llm() -> dict:
    """Checks whether at least one LLM provider API key is configured."""
    groq = os.getenv("GROQ_API_KEY", "")
    if groq and groq != "your_groq_api_key_here":
        return {"service": "llm", "label": "LLM (Groq)", "status": "ok"}
    return {
        "service": "llm",
        "label": "LLM (Groq)",
        "status": "offline",
        "detail": "No LLM API key set — supervisor uses keyword routing fallback.",
    }


async def _check_ollama() -> dict:
    """Checks if the Ollama embedding service is reachable."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                return {"service": "ollama", "label": "Ollama Embeddings", "status": "ok"}
            return {
                "service": "ollama",
                "label": "Ollama Embeddings",
                "status": "degraded",
                "detail": f"Ollama responded with HTTP {resp.status_code}.",
            }
    except Exception:
        return {
            "service": "ollama",
            "label": "Ollama Embeddings",
            "status": "degraded",
            "detail": "Ollama not reachable — RAG memory search returns empty results.",
        }


def _check_tavily() -> dict:
    """Checks if the Tavily search API key is configured."""
    key = os.getenv("TAVILY_API_KEY", "")
    if key and key != "your_tavily_api_key_here":
        return {"service": "tavily", "label": "Tavily Search", "status": "ok"}
    return {
        "service": "tavily",
        "label": "Tavily Search",
        "status": "offline",
        "detail": "Tavily key not set — browser agent falls back to DuckDuckGo scraping.",
    }


def _check_calcom() -> dict:
    """Checks if the Cal.com API key is configured."""
    key = os.getenv("CALCOM_API_KEY", "")
    if key and key != "your_calcom_api_key_here":
        return {"service": "calcom", "label": "Cal.com Calendar", "status": "ok"}
    return {
        "service": "calcom",
        "label": "Cal.com Calendar",
        "status": "offline",
        "detail": "Cal.com key not set — calendar agent uses in-memory mock store.",
    }


def _check_database() -> dict:
    """Checks if the database URL is configured."""
    url = os.getenv("DATABASE_URL", "")
    if url and "postgresql" in url:
        return {"service": "database", "label": "PostgreSQL", "status": "ok"}
    return {
        "service": "database",
        "label": "PostgreSQL",
        "status": "offline",
        "detail": "DATABASE_URL not configured.",
    }


@router.get("")
async def get_system_status() -> dict:
    """Returns the overall system health and per-service status."""
    services = [
        _check_llm(),
        _check_database(),
        _check_tavily(),
        _check_calcom(),
    ]

    # Ollama requires a network check — run it async
    services.append(await _check_ollama())

    # Determine overall status
    statuses = [s["status"] for s in services]
    if all(s == "ok" for s in statuses):
        overall = "healthy"
    elif any(s == "ok" for s in statuses):
        overall = "degraded"
    else:
        overall = "offline"

    return {
        "overall": overall,
        "auth_enabled": is_auth_enabled(),
        "services": services,
    }
