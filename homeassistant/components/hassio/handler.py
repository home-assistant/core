"""Handler for Hass.io."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
import os
from typing import Any

from aiohasupervisor import SupervisorClient
from aiohasupervisor.models import SupervisorOptions
import aiohttp
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.singleton import singleton

from .const import ATTR_MESSAGE, ATTR_RESULT, DATA_COMPONENT, X_HASS_SOURCE

_LOGGER = logging.getLogger(__name__)

KEY_SUPERVISOR_CLIENT = "supervisor_client"


class HassioAPIError(RuntimeError):
    """Return if a API trow a error."""


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
