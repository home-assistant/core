"""Frontend view for Insteon development."""

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_create_clientsession


class InsteonFrontendDev(HomeAssistantView):
    """Dev View Class for Insteon."""

    requested_file = None
    url = r"/insteonfiles/{requested_file:.+}"

    def __init__(self, hass, frontend_url: str) -> None:
        """Init the InsteonFrontendDev class."""

        self._session = async_create_clientsession(hass, verify_ssl=False)
        self.requires_auth = False
        self.name = "insteon_files:frontend"
        if frontend_url.endswith("/"):
            frontend_url = frontend_url[:-1]
        self._url_base = frontend_url

    async def get(self, request, requested_file):
        """Handle Insteon Web requests."""
        self.requested_file = requested_file
        requested = requested_file.split("/")[-1]
        url = f"{self._url_base}/{requested}"
        request = await self._session.get(url)
        if request.status == 200:
            result = await request.read()
            response = web.Response(body=result)
            response.headers["Content-Type"] = "application/javascript"

            return response
