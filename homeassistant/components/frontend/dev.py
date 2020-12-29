"""Development helpers for the frontend."""
import aiohttp
from aiohttp import hdrs, web

from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client


@callback
def async_setup_frontend_dev(hass: HomeAssistant) -> None:
    """Set up frontend dev views."""
    hass.http.register_view(  # type: ignore
        FrontendDevView(
            "http://localhost:8000", aiohttp_client.async_get_clientsession(hass)
        )
    )


FILTER_RESPONSE_HEADERS = {hdrs.CONTENT_LENGTH, hdrs.CONTENT_ENCODING}


class FrontendDevView(HomeAssistantView):
    """Frontend dev view."""

    name = "_dev:frontend"
    url = "/_dev_frontend/{path:.*}"
    requires_auth = False
    extra_urls = ["/__web-dev-server__/{path:.*}"]

    def __init__(self, forward_base: str, websession: aiohttp.ClientSession):
        """Initialize a Hass.io ingress view."""
        self._forward_base = forward_base
        self._websession = websession

    async def get(self, request: web.Request, path: str) -> web.Response:
        """Frontend routing."""
        # To deal with: import * as commonjsHelpers from '/__web-dev-server__/rollup/commonjsHelpers.js
        if request.path.startswith("/__web-dev-server__/"):
            path = f"__web-dev-server__/{path}"

        url = f"{self._forward_base}/{path}"

        if request.query_string:
            url += f"?{request.query_string}"

        async with self._websession.get(
            url,
            headers=request.headers,
            allow_redirects=False,
        ) as result:
            return web.Response(
                headers={
                    hdr: val
                    for hdr, val in result.headers.items()
                    if hdr not in FILTER_RESPONSE_HEADERS
                },
                status=result.status,
                body=await result.read(),
            )
