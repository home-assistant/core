"""Middleware to set the request context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp.web import Application, Request, StreamResponse, middleware

from homeassistant.core import callback
from homeassistant.helpers.http import current_request  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from contextvars import ContextVar


@callback
def setup_request_context(
    app: Application, context: ContextVar[Request | None]
) -> None:
    """Create request context middleware for the app."""

    @middleware
    async def request_context_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Request context middleware."""
        context.set(request)
        return await handler(request)

    app.middlewares.append(request_context_middleware)
