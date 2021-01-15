"""Middleware to add some basic security filtering to requests."""
import logging
import re

from aiohttp.web import HTTPBadRequest, middleware

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

# mypy: allow-untyped-defs

# fmt: off
FILTERS = re.compile(
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
def setup_security_filter(app):
    """Create security filter middleware for the app."""

    @middleware
    async def security_filter_middleware(request, handler):
        """Process request and block commonly known exploit attempts."""
        if FILTERS.search(request.raw_path):
            _LOGGER.warning(
                "Filtered a potential harmful request to: %s", request.raw_path
            )
            raise HTTPBadRequest

        return await handler(request)

    app.middlewares.append(security_filter_middleware)
