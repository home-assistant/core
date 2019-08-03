"""Provide CORS support for the HTTP component."""
from aiohttp.web_urldispatcher import Resource, ResourceRoute, StaticResource
from aiohttp.hdrs import ACCEPT, CONTENT_TYPE, ORIGIN, AUTHORIZATION

from homeassistant.const import HTTP_HEADER_HA_AUTH, HTTP_HEADER_X_REQUESTED_WITH
from homeassistant.core import callback

ALLOWED_CORS_HEADERS = [
    ORIGIN,
    ACCEPT,
    HTTP_HEADER_X_REQUESTED_WITH,
    CONTENT_TYPE,
    HTTP_HEADER_HA_AUTH,
    AUTHORIZATION,
]
VALID_CORS_TYPES = (Resource, ResourceRoute, StaticResource)


@callback
def setup_cors(app, origins):
    """Set up CORS."""
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

    def _allow_cors(route, config=None):
        """Allow CORS on a route."""
        if hasattr(route, "resource"):
            path = route.resource
        else:
            path = route

        if not isinstance(path, VALID_CORS_TYPES):
            return

        path = path.canonical

        if path in cors_added:
            return

        cors.add(route, config)
        cors_added.add(path)

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

    async def cors_startup(app):
        """Initialize CORS when app starts up."""
        for resource in list(app.router.resources()):
            _allow_cors(resource)

    app.on_startup.append(cors_startup)
