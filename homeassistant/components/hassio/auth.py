"""Implement the auth feature from Hass.io for Add-ons."""
from ipaddress import ip_address
import logging
import os

from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPUnauthorized,
)
import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_HASS_USER, KEY_REAL_IP
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import HTTP_OK
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_ADDON, ATTR_PASSWORD, ATTR_USERNAME

_LOGGER = logging.getLogger(__name__)


SCHEMA_API_AUTH = vol.Schema(
    {
        vol.Required(ATTR_USERNAME): cv.string,
        vol.Required(ATTR_PASSWORD): cv.string,
        vol.Required(ATTR_ADDON): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_API_PASSWORD_RESET = vol.Schema(
    {vol.Required(ATTR_USERNAME): cv.string, vol.Required(ATTR_PASSWORD): cv.string},
    extra=vol.ALLOW_EXTRA,
)


@callback
def async_setup_auth_view(hass: HomeAssistantType, user: User):
    """Auth setup."""
    hassio_auth = HassIOAuth(hass, user)
    hassio_password_reset = HassIOPasswordReset(hass, user)

    hass.http.register_view(hassio_auth)
    hass.http.register_view(hassio_password_reset)


class HassIOBaseAuth(HomeAssistantView):
    """Hass.io view to handle auth requests."""

    def __init__(self, hass: HomeAssistantType, user: User):
        """Initialize WebView."""
        self.hass = hass
        self.user = user

    def _check_access(self, request: web.Request):
        """Check if this call is from Supervisor."""
        # Check caller IP
        hassio_ip = os.environ["HASSIO"].split(":")[0]
        if request[KEY_REAL_IP] != ip_address(hassio_ip):
            _LOGGER.error("Invalid auth request from %s", request[KEY_REAL_IP])
            raise HTTPUnauthorized()

        # Check caller token
        if request[KEY_HASS_USER].id != self.user.id:
            _LOGGER.error("Invalid auth request from %s", request[KEY_HASS_USER].name)
            raise HTTPUnauthorized()

    def _get_provider(self):
        """Return Homeassistant auth provider."""
        prv = self.hass.auth.get_auth_provider("homeassistant", None)
        if prv is not None:
            return prv

        _LOGGER.error("Can't find Home Assistant auth")
        raise HTTPNotFound()


class HassIOAuth(HassIOBaseAuth):
    """Hass.io view to handle auth requests."""

    name = "api:hassio:auth"
    url = "/api/hassio_auth"

    @RequestDataValidator(SCHEMA_API_AUTH)
    async def post(self, request, data):
        """Handle auth requests."""
        self._check_access(request)

        await self._check_login(data[ATTR_USERNAME], data[ATTR_PASSWORD])
        return web.Response(status=HTTP_OK)

    async def _check_login(self, username, password):
        """Check User credentials."""
        provider = self._get_provider()

        try:
            await provider.async_validate_login(username, password)
        except HomeAssistantError:
            raise HTTPUnauthorized() from None


class HassIOPasswordReset(HassIOBaseAuth):
    """Hass.io view to handle password reset requests."""

    name = "api:hassio:auth:password:reset"
    url = "/api/hassio_auth/password_reset"

    @RequestDataValidator(SCHEMA_API_PASSWORD_RESET)
    async def post(self, request, data):
        """Handle password reset requests."""
        self._check_access(request)

        await self._change_password(data[ATTR_USERNAME], data[ATTR_PASSWORD])
        return web.Response(status=HTTP_OK)

    async def _change_password(self, username, password):
        """Check User credentials."""
        provider = self._get_provider()

        try:
            await self.hass.async_add_executor_job(
                provider.data.change_password, username, password
            )
            await provider.data.async_save()
        except HomeAssistantError:
            raise HTTPInternalServerError()
