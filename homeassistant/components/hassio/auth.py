"""Implement the auth feature from Hass.io for Add-ons."""
from ipaddress import ip_address
import logging
import os

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound, HTTPUnauthorized
import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.auth.providers import homeassistant as auth_ha
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_HASS_USER
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import HTTP_OK
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_ADDON, ATTR_PASSWORD, ATTR_USERNAME

_LOGGER = logging.getLogger(__name__)


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
        if ip_address(request.transport.get_extra_info("peername")[0]) != ip_address(
            hassio_ip
        ):
            _LOGGER.error("Invalid auth request from %s", request.remote)
            raise HTTPUnauthorized()

        # Check caller token
        if request[KEY_HASS_USER].id != self.user.id:
            _LOGGER.error("Invalid auth request from %s", request[KEY_HASS_USER].name)
            raise HTTPUnauthorized()


class HassIOAuth(HassIOBaseAuth):
    """Hass.io view to handle auth requests."""

    name = "api:hassio:auth"
    url = "/api/hassio_auth"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required(ATTR_USERNAME): cv.string,
                vol.Required(ATTR_PASSWORD): cv.string,
                vol.Required(ATTR_ADDON): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
    async def post(self, request, data):
        """Handle auth requests."""
        self._check_access(request)
        provider = auth_ha.async_get_provider(request.app["hass"])

        try:
            await provider.async_validate_login(
                data[ATTR_USERNAME], data[ATTR_PASSWORD]
            )
        except auth_ha.InvalidAuth:
            raise HTTPNotFound() from None

        return web.Response(status=HTTP_OK)


class HassIOPasswordReset(HassIOBaseAuth):
    """Hass.io view to handle password reset requests."""

    name = "api:hassio:auth:password:reset"
    url = "/api/hassio_auth/password_reset"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required(ATTR_USERNAME): cv.string,
                vol.Required(ATTR_PASSWORD): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
    async def post(self, request, data):
        """Handle password reset requests."""
        self._check_access(request)
        provider = auth_ha.async_get_provider(request.app["hass"])

        try:
            await provider.async_change_password(
                data[ATTR_USERNAME], data[ATTR_PASSWORD]
            )
        except auth_ha.InvalidUser as err:
            raise HTTPNotFound() from err

        return web.Response(status=HTTP_OK)
