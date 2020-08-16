"""Handler for Hass.io."""
import asyncio
import logging
import os

import aiohttp
import async_timeout

from homeassistant.components.http import (
    CONF_SERVER_HOST,
    CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE,
)
from homeassistant.const import HTTP_BAD_REQUEST, HTTP_OK, SERVER_PORT

from .const import X_HASSIO

_LOGGER = logging.getLogger(__name__)


class HassioAPIError(RuntimeError):
    """Return if a API trow a error."""


def _api_bool(funct):
    """Return a boolean."""

    async def _wrapper(*argv, **kwargs):
        """Wrap function."""
        try:
            data = await funct(*argv, **kwargs)
            return data["result"] == "ok"
        except HassioAPIError:
            return False

    return _wrapper


def _api_data(funct):
    """Return data of an api."""

    async def _wrapper(*argv, **kwargs):
        """Wrap function."""
        data = await funct(*argv, **kwargs)
        if data["result"] == "ok":
            return data["data"]
        raise HassioAPIError(data["message"])

    return _wrapper


class HassIO:
    """Small API wrapper for Hass.io."""

    def __init__(self, loop, websession, ip):
        """Initialize Hass.io API."""
        self.loop = loop
        self.websession = websession
        self._ip = ip

    @_api_bool
    def is_connected(self):
        """Return true if it connected to Hass.io supervisor.

        This method return a coroutine.
        """
        return self.send_command("/supervisor/ping", method="get", timeout=15)

    @_api_data
    def get_info(self):
        """Return generic Supervisor information.

        This method return a coroutine.
        """
        return self.send_command("/info", method="get")

    @_api_data
    def get_host_info(self):
        """Return data for Host.

        This method return a coroutine.
        """
        return self.send_command("/host/info", method="get")

    @_api_data
    def get_core_info(self):
        """Return data for Home Asssistant Core.

        This method returns a coroutine.
        """
        return self.send_command("/core/info", method="get")

    @_api_data
    def get_addon_info(self, addon):
        """Return data for a Add-on.

        This method return a coroutine.
        """
        return self.send_command(f"/addons/{addon}/info", method="get")

    @_api_data
    def get_ingress_panels(self):
        """Return data for Add-on ingress panels.

        This method return a coroutine.
        """
        return self.send_command("/ingress/panels", method="get")

    @_api_bool
    def restart_homeassistant(self):
        """Restart Home-Assistant container.

        This method return a coroutine.
        """
        return self.send_command("/homeassistant/restart")

    @_api_bool
    def stop_homeassistant(self):
        """Stop Home-Assistant container.

        This method return a coroutine.
        """
        return self.send_command("/homeassistant/stop")

    @_api_data
    def retrieve_discovery_messages(self):
        """Return all discovery data from Hass.io API.

        This method return a coroutine.
        """
        return self.send_command("/discovery", method="get")

    @_api_data
    def get_discovery_message(self, uuid):
        """Return a single discovery data message.

        This method return a coroutine.
        """
        return self.send_command(f"/discovery/{uuid}", method="get")

    @_api_bool
    async def update_hass_api(self, http_config, refresh_token):
        """Update Home Assistant API data on Hass.io."""
        port = http_config.get(CONF_SERVER_PORT) or SERVER_PORT
        options = {
            "ssl": CONF_SSL_CERTIFICATE in http_config,
            "port": port,
            "watchdog": True,
            "refresh_token": refresh_token.token,
        }

        if http_config.get(CONF_SERVER_HOST) is not None:
            options["watchdog"] = False
            _LOGGER.warning(
                "Found incompatible HTTP option 'server_host'. Watchdog feature disabled"
            )

        return await self.send_command("/homeassistant/options", payload=options)

    @_api_bool
    def update_hass_timezone(self, timezone):
        """Update Home-Assistant timezone data on Hass.io.

        This method return a coroutine.
        """
        return self.send_command("/supervisor/options", payload={"timezone": timezone})

    async def send_command(self, command, method="post", payload=None, timeout=10):
        """Send API command to Hass.io.

        This method is a coroutine.
        """
        try:
            with async_timeout.timeout(timeout):
                request = await self.websession.request(
                    method,
                    f"http://{self._ip}{command}",
                    json=payload,
                    headers={X_HASSIO: os.environ.get("HASSIO_TOKEN", "")},
                )

                if request.status not in (HTTP_OK, HTTP_BAD_REQUEST):
                    _LOGGER.error("%s return code %d", command, request.status)
                    raise HassioAPIError()

                answer = await request.json()
                return answer

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        raise HassioAPIError()
