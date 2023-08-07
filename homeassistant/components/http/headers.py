"""Middleware that helps with the control of headers in our responses."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiohttp.web import Application, Request, StreamResponse, middleware

from homeassistant.core import callback


@callback
def setup_headers(app: Application, use_x_frame_options: bool) -> None:
    """Create headers middleware for the app."""

    @middleware
    async def headers_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Process request and add headers to the responses."""
        response = await handler(request)
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Set an empty server header, to prevent aiohttp of setting one.
        response.headers["Server"] = ""

        if use_x_frame_options:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"

        return response

    app.middlewares.append(headers_middleware)
