"""Handler for Hass.io."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from http import HTTPStatus
import logging
import os
from typing import Any

from aiohasupervisor import SupervisorClient
from aiohasupervisor.models import SupervisorOptions
import aiohttp
from yarl import URL

from homeassistant.auth.models import RefreshToken
from homeassistant.components.http import (
    CONF_SERVER_HOST,
    CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE,
)
from homeassistant.const import SERVER_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.singleton import singleton

from .const import ATTR_MESSAGE, ATTR_RESULT, DATA_COMPONENT, X_HASS_SOURCE

_LOGGER = logging.getLogger(__name__)

KEY_SUPERVISOR_CLIENT = "supervisor_client"


class HassioAPIError(RuntimeError):
    """Return if a API trow a error."""


def _api_bool[**_P](
    funct: Callable[_P, Coroutine[Any, Any, dict[str, Any]]],
) -> Callable[_P, Coroutine[Any, Any, bool]]:
    """Return a boolean."""

    async def _wrapper(*argv: _P.args, **kwargs: _P.kwargs) -> bool:
        """Wrap function."""
        try:
            data = await funct(*argv, **kwargs)
            return data["result"] == "ok"
        except HassioAPIError:
            return False

    return _wrapper


def api_data[**_P](
    funct: Callable[_P, Coroutine[Any, Any, dict[str, Any]]],
) -> Callable[_P, Coroutine[Any, Any, Any]]:
    """Return data of an api."""

    async def _wrapper(*argv: _P.args, **kwargs: _P.kwargs) -> Any:
        """Wrap function."""
        data = await funct(*argv, **kwargs)
        if data["result"] == "ok":
            return data["data"]
        raise HassioAPIError(data["message"])

    return _wrapper


class HassIO:
    """Small API wrapper for Hass.io."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        websession: aiohttp.ClientSession,
        ip: str,
    ) -> None:
        """Initialize Hass.io API."""
        self.loop = loop
        self.websession = websession
        self._ip = ip
        base_url = f"http://{ip}"
        self._base_url = URL(base_url)

    @property
    def base_url(self) -> URL:
        """Return base url for Supervisor."""
        return self._base_url

    @api_data
    def get_info(self) -> Coroutine:
        """Return generic Supervisor information.

        This method returns a coroutine.
        """
        return self.send_command("/info", method="get")

    @api_data
    def get_host_info(self) -> Coroutine:
        """Return data for Host.

        This method returns a coroutine.
        """
        return self.send_command("/host/info", method="get")

    @api_data
    def get_os_info(self) -> Coroutine:
        """Return data for the OS.

        This method returns a coroutine.
        """
        return self.send_command("/os/info", method="get")

    @api_data
    def get_core_info(self) -> Coroutine:
        """Return data for Home Asssistant Core.

        This method returns a coroutine.
        """
        return self.send_command("/core/info", method="get")

    @api_data
    def get_supervisor_info(self) -> Coroutine:
        """Return data for the Supervisor.

        This method returns a coroutine.
        """
        return self.send_command("/supervisor/info", method="get")

    @api_data
    def get_network_info(self) -> Coroutine:
        """Return data for the Host Network.

        This method returns a coroutine.
        """
        return self.send_command("/network/info", method="get")

    @api_data
    def get_core_stats(self) -> Coroutine:
        """Return stats for the core.

        This method returns a coroutine.
        """
        return self.send_command("/core/stats", method="get")

    @api_data
    def get_supervisor_stats(self) -> Coroutine:
        """Return stats for the supervisor.

        This method returns a coroutine.
        """
        return self.send_command("/supervisor/stats", method="get")

    @api_data
    def get_ingress_panels(self) -> Coroutine:
        """Return data for Add-on ingress panels.

        This method returns a coroutine.
        """
        return self.send_command("/ingress/panels", method="get")

    @_api_bool
    async def update_hass_api(
        self, http_config: dict[str, Any], refresh_token: RefreshToken
    ):
        """Update Home Assistant API data on Hass.io."""
        port = http_config.get(CONF_SERVER_PORT) or SERVER_PORT
        options = {
            "ssl": CONF_SSL_CERTIFICATE in http_config,
            "port": port,
            "refresh_token": refresh_token.token,
        }

        if http_config.get(CONF_SERVER_HOST) is not None:
            options["watchdog"] = False
            _LOGGER.warning(
                "Found incompatible HTTP option 'server_host'. Watchdog feature"
                " disabled"
            )

        return await self.send_command("/homeassistant/options", payload=options)

    @_api_bool
    def update_hass_config(self, timezone: str, country: str | None) -> Coroutine:
        """Update Home-Assistant timezone data on Hass.io.

        This method returns a coroutine.
        """
        return self.send_command(
            "/supervisor/options", payload={"timezone": timezone, "country": country}
        )

    async def send_command(
        self,
        command: str,
        method: str = "post",
        payload: Any | None = None,
        timeout: int | None = 10,
        return_text: bool = False,
        *,
        params: dict[str, Any] | None = None,
        source: str = "core.handler",
    ) -> Any:
        """Send API command to Hass.io.

        This method is a coroutine.
        """
        joined_url = self._base_url.with_path(command)
        # This check is to make sure the normalized URL string
        # is the same as the URL string that was passed in. If
        # they are different, then the passed in command URL
        # contained characters that were removed by the normalization
        # such as ../../../../etc/passwd
        if joined_url.raw_path != command:
            _LOGGER.error("Invalid request %s", command)
            raise HassioAPIError

        try:
            response = await self.websession.request(
                method,
                joined_url,
                params=params,
                json=payload,
                headers={
                    aiohttp.hdrs.AUTHORIZATION: (
                        f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}"
                    ),
                    X_HASS_SOURCE: source,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            )

            if response.status != HTTPStatus.OK:
                error = await response.json(encoding="utf-8")
                if error.get(ATTR_RESULT) == "error":
                    raise HassioAPIError(error.get(ATTR_MESSAGE))

                _LOGGER.error(
                    "Request to %s method %s returned with code %d",
                    command,
                    method,
                    response.status,
                )
                raise HassioAPIError

            if return_text:
                return await response.text(encoding="utf-8")

            return await response.json(encoding="utf-8")

        except TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        raise HassioAPIError


@singleton(KEY_SUPERVISOR_CLIENT)
def get_supervisor_client(hass: HomeAssistant) -> SupervisorClient:
    """Return supervisor client."""
    hassio = hass.data[DATA_COMPONENT]
    return SupervisorClient(
        str(hassio.base_url),
        os.environ.get("SUPERVISOR_TOKEN", ""),
        session=hassio.websession,
    )


async def async_update_diagnostics(hass: HomeAssistant, diagnostics: bool) -> None:
    """Update Supervisor diagnostics toggle.

    The caller of the function should handle SupervisorError.
    """
    await get_supervisor_client(hass).supervisor.set_options(
        SupervisorOptions(diagnostics=diagnostics)
    )
