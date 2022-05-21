"""Middleware to set the request context."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from aiohttp.web import Application, Request, StreamResponse, middleware

from homeassistant.core import callback

current_request: ContextVar[Request | None] = ContextVar(
    "current_request", default=None
)


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
