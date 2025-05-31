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

from .const import KEY_HASS

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

NOTIFICATION_ID_FILTER: Final = "ip_filter"

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

        base_msg = None
        for unsafe_byte in UNSAFE_URL_BYTES:
            if unsafe_byte in path_with_query_string:
                if unsafe_byte in request.query_string:
                    base_msg = "Filtered a request from {ip} with unsafe byte query string: {path}"
                    break

                base_msg = (
                    "Filtered a request from {ip} with an unsafe byte in path: {path}"
                )
                break

        if base_msg is None:
            if FILTERS.search(_recursive_unquote(path_with_query_string)):
                # Check the full path with query string first, if its
                # a hit, than check just the query string to give a more
                # specific warning.
                if FILTERS.search(_recursive_unquote(request.query_string)):
                    base_msg = "Filtered a request from {ip} with a potential harmful query string: {path}"
                else:
                    base_msg = (
                        "Filtered a potential harmful request from {ip} to: {path}"
                    )

        if base_msg is not None:
            # Circular import with websocket_api
            # pylint: disable=import-outside-toplevel
            from ipaddress import ip_address

            from homeassistant.components import persistent_notification

            ip_address_ = ip_address(request.remote)  # type: ignore[arg-type]
            hass = request.app[KEY_HASS]
            msg = base_msg.format(ip=ip_address_, path=request.path)
            _LOGGER.warning(msg)
            persistent_notification.async_create(
                hass,
                f"{msg}, see log for details",
                "Filtered request",
                NOTIFICATION_ID_FILTER,
            )

            raise HTTPBadRequest

        return await handler(request)

    app.middlewares.append(security_filter_middleware)
