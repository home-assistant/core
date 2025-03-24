"""Middleware to add some basic security filtering to requests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import lru_cache
import logging
import re
from typing import Final
from urllib.parse import unquote

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

# Unsafe bytes to be removed per WHATWG spec
UNSAFE_URL_BYTES = ["\t", "\r", "\n"]


@callback
def setup_security_filter(app: Application) -> None:
    """Create security filter middleware for the app."""

    @lru_cache
    def _recursive_unquote(value: str) -> str:
        """Handle values that are encoded multiple times."""
        if (unquoted := unquote(value)) != value:
            unquoted = _recursive_unquote(unquoted)
        return unquoted

    @middleware
    async def security_filter_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Process request and block commonly known exploit attempts."""
        path_with_query_string = f"{request.path}?{request.query_string}"

        for unsafe_byte in UNSAFE_URL_BYTES:
            if unsafe_byte in path_with_query_string:
                if unsafe_byte in request.query_string:
                    _LOGGER.warning(
                        "Filtered a request with unsafe byte query string: %s",
                        request.raw_path,
                    )
                    raise HTTPBadRequest
                _LOGGER.warning(
                    "Filtered a request with an unsafe byte in path: %s",
                    request.raw_path,
                )
                raise HTTPBadRequest

        if FILTERS.search(_recursive_unquote(path_with_query_string)):
            # Check the full path with query string first, if its
            # a hit, than check just the query string to give a more
            # specific warning.
            if FILTERS.search(_recursive_unquote(request.query_string)):
                _LOGGER.warning(
                    "Filtered a request with a potential harmful query string: %s",
                    request.raw_path,
                )
                raise HTTPBadRequest

            _LOGGER.warning(
                "Filtered a potential harmful request to: %s", request.raw_path
            )
            raise HTTPBadRequest

        return await handler(request)

    app.middlewares.append(security_filter_middleware)
