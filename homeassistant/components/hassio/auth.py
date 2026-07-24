"""Implement the auth feature from Hass.io for Add-ons."""

from http import HTTPStatus
from ipaddress import ip_address
import logging
import os

from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPNotFound,
    HTTPServiceUnavailable,
    HTTPUnauthorized,
)
import voluptuous as vol

from homeassistant.auth.providers import homeassistant as auth_ha
from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView
from homeassistant.components.http.const import is_supervisor_unix_socket_request
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import ATTR_ADDON, ATTR_PASSWORD, ATTR_USERNAME, DATA_HASSIO_SUPERVISOR_USER

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_auth_view(hass: HomeAssistant) -> None:
    """Auth setup."""
    hass.http.register_view(HassIOAuth(hass))
    hass.http.register_view(HassIOPasswordReset(hass))


class HassIOBaseAuth(HomeAssistantView):
    """Hass.io view to handle auth requests."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize WebView."""
        self.hass = hass

    def _check_access(self, request: web.Request) -> None:
        """Check if this call is from Supervisor."""
        user = self.hass.data.get(DATA_HASSIO_SUPERVISOR_USER)
        if user is None:
            raise HTTPServiceUnavailable

        # Requests over the Supervisor Unix socket are authenticated by the
        # http auth middleware as the Supervisor user, so the caller-IP check
        # below does not apply (and would crash, since `peername` is empty for
        # Unix sockets). The user-ID check still runs to ensure only the
        # Supervisor user can reach this endpoint.
        if not is_supervisor_unix_socket_request(request):
            hassio_ip = os.environ["SUPERVISOR"].split(":")[0]
            assert request.transport
            peername = request.transport.get_extra_info("peername")
            if not peername or ip_address(peername[0]) != ip_address(hassio_ip):
                _LOGGER.error("Invalid auth request from %s", request.remote)
                raise HTTPUnauthorized

        # Check caller token
        if request[KEY_HASS_USER].id != user.id:
            _LOGGER.error("Invalid auth request from %s", request[KEY_HASS_USER].name)
            raise HTTPUnauthorized


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
    async def post(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Handle auth requests."""
        self._check_access(request)
        provider = auth_ha.async_get_provider(request.app[KEY_HASS])

        try:
            await provider.async_validate_login(
                data[ATTR_USERNAME], data[ATTR_PASSWORD]
            )
        except auth_ha.InvalidAuth:
            raise HTTPNotFound from None

        return web.Response(status=HTTPStatus.OK)


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
    async def post(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Handle password reset requests."""
        self._check_access(request)
        provider = auth_ha.async_get_provider(request.app[KEY_HASS])

        try:
            await provider.async_change_password(
                data[ATTR_USERNAME], data[ATTR_PASSWORD]
            )
        except auth_ha.InvalidUser as err:
            raise HTTPNotFound from err

        return web.Response(status=HTTPStatus.OK)
