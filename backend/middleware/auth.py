"""API key authentication middleware.

When OMNIPILOT_API_KEY is set in the environment, all /api/* requests must
include the header ``X-API-Key: <key>``. When the key is unset or empty,
authentication is disabled (development mode).

The middleware also resolves the authenticated user and attaches it to
``request.state.user_id`` so downstream handlers can scope queries.
"""

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# Paths that are always public — no auth required.
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/api/status", "/"})

# Static file prefixes that should never require auth.
_STATIC_PREFIXES: tuple[str, ...] = ("/assets/", "/favicon")


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return True
    for prefix in _STATIC_PREFIXES:
        if path.startswith(prefix):
            return True
    # FastAPI docs / openapi
    if path in ("/docs", "/redoc", "/openapi.json"):
        return True
    return False


def is_auth_enabled() -> bool:
    """Returns True when API key auth is active."""
    key = os.getenv("OMNIPILOT_API_KEY", "")
    return bool(key and key != "your_omnipilot_api_key_here")


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validates the X-API-Key header on all /api/* requests when auth is enabled."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not is_auth_enabled() or _is_public(request.url.path):
            return await call_next(request)

        # For API routes, require the header
        if request.url.path.startswith("/api/"):
            provided = request.headers.get("X-API-Key", "")
            expected = os.getenv("OMNIPILOT_API_KEY", "")
            if provided != expected:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key. Provide X-API-Key header."},
                )

        return await call_next(request)
