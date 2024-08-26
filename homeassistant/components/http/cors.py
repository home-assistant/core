"""Provide CORS support for the HTTP component."""

from __future__ import annotations

from typing import Final, cast

from aiohttp.hdrs import ACCEPT, AUTHORIZATION, CONTENT_TYPE, ORIGIN
from aiohttp.web import Application
from aiohttp.web_urldispatcher import (
    AbstractResource,
    AbstractRoute,
    Resource,
    ResourceRoute,
    StaticResource,
)
import aiohttp_cors

from homeassistant.const import HTTP_HEADER_X_REQUESTED_WITH
from homeassistant.core import callback
from homeassistant.helpers.http import (
    KEY_ALLOW_ALL_CORS,
    KEY_ALLOW_CONFIGURED_CORS,
    AllowCorsType,
)

ALLOWED_CORS_HEADERS: Final[list[str]] = [
    ORIGIN,
    ACCEPT,
    HTTP_HEADER_X_REQUESTED_WITH,
    CONTENT_TYPE,
    AUTHORIZATION,
]
VALID_CORS_TYPES: Final = (Resource, ResourceRoute, StaticResource)


@callback
def setup_cors(app: Application, origins: list[str]) -> None:
    """Set up CORS."""
    cors = aiohttp_cors.setup(
        app,
        defaults={
            host: aiohttp_cors.ResourceOptions(
                allow_headers=ALLOWED_CORS_HEADERS, allow_methods="*"
            )
            for host in origins
        },
    )

    cors_added = set()

    def _allow_cors(
        route: AbstractRoute | AbstractResource,
        config: dict[str, aiohttp_cors.ResourceOptions] | None = None,
    ) -> None:
        """Allow CORS on a route."""
        if isinstance(route, AbstractRoute):
            path = route.resource
        else:
            path = route

        if not isinstance(path, VALID_CORS_TYPES):
            return

        path_str = path.canonical

        if path_str.startswith("/api/hassio_ingress/"):
            return

        if path_str in cors_added:
            return

        cors.add(route, config)
        cors_added.add(path_str)

    app[KEY_ALLOW_ALL_CORS] = lambda route: _allow_cors(
        route,
        {
            "*": aiohttp_cors.ResourceOptions(
                allow_headers=ALLOWED_CORS_HEADERS, allow_methods="*"
            )
        },
    )

    if origins:
        app[KEY_ALLOW_CONFIGURED_CORS] = cast(AllowCorsType, _allow_cors)
    else:
        app[KEY_ALLOW_CONFIGURED_CORS] = lambda _: None
