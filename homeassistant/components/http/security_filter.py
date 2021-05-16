"""Middleware to add some basic security filtering to requests."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
import re
from typing import Final

from aiohttp.web import Application, HTTPBadRequest, Request, StreamResponse, middleware

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

# fmt: off
FILTERS: Final = re.compile(
    r"(?:"

    # Common exploits
    r"proc/self/environ"
    r"|(<|%3C).*script.*(>|%3E)"

    # File Injections
    r"|(\.\.//?)+"  # ../../anywhere
    r"|[a-zA-Z0-9_]=/([a-z0-9_.]//?)+"  # .html?v=/.//test

    # SQL Injections
    r"|union.*select.*\("
    r"|union.*all.*select.*"
    r"|concat.*\("

    r")",
    flags=re.IGNORECASE,
)
# fmt: on


@callback
def setup_security_filter(app: Application) -> None:
    """Create security filter middleware for the app."""

    @middleware
    async def security_filter_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Process request and tblock commonly known exploit attempts."""
        if FILTERS.search(request.path):
            _LOGGER.warning(
                "Filtered a potential harmful request to: %s", request.raw_path
            )
            raise HTTPBadRequest

        if FILTERS.search(request.query_string):
            _LOGGER.warning(
                "Filtered a request with a potential harmful query string: %s",
                request.raw_path,
            )
            raise HTTPBadRequest

        return await handler(request)

    app.middlewares.append(security_filter_middleware)
