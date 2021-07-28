"""Provide CORS support for the HTTP component."""
from __future__ import annotations

from typing import Final

from aiohttp.hdrs import ACCEPT, AUTHORIZATION, CONTENT_TYPE, ORIGIN
from aiohttp.web import Application
from aiohttp.web_urldispatcher import (
    AbstractResource,
    AbstractRoute,
    Resource,
    ResourceRoute,
    StaticResource,
)

from homeassistant.const import HTTP_HEADER_X_REQUESTED_WITH
from homeassistant.core import callback

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
    # This import should remain here. That way the HTTP integration can always
    # be imported by other integrations without it's requirements being installed.
    # pylint: disable=import-outside-toplevel
    import aiohttp_cors

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

    app["allow_cors"] = lambda route: _allow_cors(
        route,
        {
            "*": aiohttp_cors.ResourceOptions(
                allow_headers=ALLOWED_CORS_HEADERS, allow_methods="*"
            )
        },
    )

    if not origins:
        return

    async def cors_startup(app: Application) -> None:
        """Initialize CORS when app starts up."""
        for resource in list(app.router.resources()):
            _allow_cors(resource)

    app.on_startup.append(cors_startup)
