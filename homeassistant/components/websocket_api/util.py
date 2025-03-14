"""Websocket API util.""."""

from __future__ import annotations

from aiohttp import web


def describe_request(request: web.Request) -> str:
    """Describe a request."""
    description = f"from {request.remote}"
    if user_agent := request.headers.get("user-agent"):
        description += f" ({user_agent})"
    return description
