"""Represent the FortiGate firewall and its devices and sensors."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import REST_TIMEOUT


class FortiOSAPI:
    """FortiOS API wrapper."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        token: str,
        vdom: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize the FortiOS API wrapper."""
        self._hass = hass
        self._host = host
        self._port = port
        self._token = token
        self._vdom = vdom
        self._verify_ssl = verify_ssl

    async def get(self, path: str) -> dict[str, Any]:
        """Perform a GET request."""
        url = f"https://{self._host}:{self._port}/api/v2/{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        parameters = {"vdom": self._vdom}

        session = async_get_clientsession(self._hass)
        async with session.get(
            url,
            headers=headers,
            params=parameters,
            timeout=ClientTimeout(total=REST_TIMEOUT),
            ssl=self._verify_ssl,
        ) as response:
            response.raise_for_status()
            return await response.json()
