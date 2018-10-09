"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging

from aiohttp import web

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView


_LOGGER = logging.getLogger(__name__)

ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'


@callback
def async_setup_auth(hass):
    """Auth setup."""
    hassio_auth = HassIOAuth(hass)
    hass.http.register_view(hassio_auth)


class HassIOAuth(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_auth"
    url = "/api/hassio_auth"

    def __init__(self, hass):
        """Initialize WebView."""
        self.hass = hass

    async def post(self, request):
        """Handle new discovery requests."""
        data = await request.json()
