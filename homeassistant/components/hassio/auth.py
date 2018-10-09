"""Implement the auth feature from Hass.io for Add-ons."""
import asyncio
import logging
import os

from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPForbidden, HTTPNotFound, HTTPOk, HTTPUnauthorized)

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
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
        await self._check_login(data[ATTR_USERNAME], data[ATTR_PASSWORD])

    def _get_provider(self):
        """Return Homeassistant auth provider."""
        for prv in hass.auth.auth_provider:
            if prv.type == 'homeassistant':
                return prv

        _LOGGER.error("Can't find Home Assistant auth.")
        raise HTTPNotFound()
        
    asnyc def _check_login(self, username, password):
        """Check User credentials."""
        provider = self._get_provider()
 
        try:
            provider.async_validate_login(username, password)
        except HomeAssistantError:
            raise HTTPUnauthorized() from None

        raise HTTPOk()
