"""Middleware that helps with the control of headers in our responses."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final

from aiohttp import hdrs
from aiohttp.web import Application, Request, StreamResponse, middleware
from aiohttp.web_exceptions import HTTPException
from multidict import CIMultiDict, istr

from homeassistant.core import callback

REFERRER_POLICY: Final[istr] = istr("Referrer-Policy")
X_CONTENT_TYPE_OPTIONS: Final[istr] = istr("X-Content-Type-Options")
X_FRAME_OPTIONS: Final[istr] = istr("X-Frame-Options")


@callback
def setup_headers(app: Application, use_x_frame_options: bool) -> None:
    """Create headers middleware for the app."""

    added_headers = CIMultiDict(
        {
            REFERRER_POLICY: "no-referrer",
            X_CONTENT_TYPE_OPTIONS: "nosniff",
            hdrs.SERVER: "",  # Empty server header, to prevent aiohttp of setting one.
        }
    )

    if use_x_frame_options:
        added_headers[X_FRAME_OPTIONS] = "SAMEORIGIN"

    @middleware
    async def headers_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Process request and add headers to the responses."""
        try:
            response = await handler(request)
        except HTTPException as err:
            err.headers.update(added_headers)
            raise

        response.headers.update(added_headers)
        return response

    app.middlewares.append(headers_middleware)
