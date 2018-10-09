"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging
import os

from aiohttp import web
from aiohttp.web_exceptions import HTTPForbidden

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_REAL_IP


_LOGGER = logging.getLogger(__name__)

ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'


@callback
def async_setup_auth(hass):
    """Auth setup."""
    hassio_ip = os.environ['HASSIO'].split(':')[0]
    hassio_auth = HassIOAuth(hass, hassio_ip)

    hass.http.register_view(hassio_auth)


class HassIOAuth(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_auth"
    url = "/api/hassio_auth"

    def __init__(self, hass, hassio_ip):
        """Initialize WebView."""
        self.hass = hass
        sel.hassio_ip = hassio_ip

    async def post(self, request):
        """Handle new discovery requests."""
        if request[KEY_REAL_IP] != hassio_ip:
            _LOGGER.error(
                "Invalid auth request from %s", request[KEY_REAL_IP])
            raise HTTPForbidden()

        data = await request.json()
