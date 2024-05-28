"""Middleware that helps with the control of headers in our responses."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiohttp.web import Application, Request, StreamResponse, middleware
from aiohttp.web_exceptions import HTTPException

from homeassistant.core import callback


@callback
def setup_headers(app: Application, use_x_frame_options: bool) -> None:
    """Create headers middleware for the app."""

    added_headers = {
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Server": "",  # Empty server header, to prevent aiohttp of setting one.
    }

    if use_x_frame_options:
        added_headers["X-Frame-Options"] = "SAMEORIGIN"

    @middleware
    async def headers_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Process request and add headers to the responses."""
        try:
            response = await handler(request)
        except HTTPException as err:
            for key, value in added_headers.items():
                err.headers[key] = value
            raise

        for key, value in added_headers.items():
            response.headers[key] = value

        return response

    app.middlewares.append(headers_middleware)
