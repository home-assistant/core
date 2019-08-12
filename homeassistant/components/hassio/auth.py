"""Implement the auth feature from Hass.io for Add-ons."""
import logging
import os
from ipaddress import ip_address

import voluptuous as vol
from aiohttp import web
from aiohttp.web_exceptions import HTTPForbidden, HTTPNotFound

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_REAL_IP
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_ADDON, ATTR_PASSWORD, ATTR_USERNAME

_LOGGER = logging.getLogger(__name__)


SCHEMA_API_AUTH = vol.Schema({
    vol.Required(ATTR_USERNAME): cv.string,
    vol.Required(ATTR_PASSWORD): cv.string,
    vol.Required(ATTR_ADDON): cv.string,
}, extra=vol.ALLOW_EXTRA)


@callback
def async_setup_auth_view(hass: HomeAssistantType):
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

    @RequestDataValidator(SCHEMA_API_AUTH)
    async def post(self, request, data):
        """Handle new discovery requests."""
        hassio_ip = os.environ['HASSIO'].split(':')[0]
        if request[KEY_REAL_IP] != ip_address(hassio_ip):
            _LOGGER.error(
                "Invalid auth request from %s", request[KEY_REAL_IP])
            raise HTTPForbidden()

        await self._check_login(data[ATTR_USERNAME], data[ATTR_PASSWORD])
        return web.Response(status=200)

    def _get_provider(self):
        """Return Homeassistant auth provider."""
        prv = self.hass.auth.get_auth_provider('homeassistant', None)
        if prv is not None:
            return prv

        _LOGGER.error("Can't find Home Assistant auth.")
        raise HTTPNotFound()

    async def _check_login(self, username, password):
        """Check User credentials."""
        provider = self._get_provider()

        try:
            await provider.async_validate_login(username, password)
        except HomeAssistantError:
            raise HTTPForbidden() from None
