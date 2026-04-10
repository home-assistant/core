"""Client for Renson WAVES API."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class RensonWavesCannotConnect(Exception):
    """Cannot connect to Renson WAVES device."""


class RensonWavesClient:
    """Renson WAVES HTTP client."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.host = host
        self.port = port
        self.session = session
        self.base_url = f"http://{host}:{port}/v1"

    async def async_get_constellation(self) -> dict[str, Any]:
        """Get constellation data from device."""
        try:
            async with self.session.get(
                f"{self.base_url}/constellation",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.debug("Error fetching constellation: %s", err)
            raise RensonWavesCannotConnect(f"Cannot reach device: {err}") from err

    async def async_get_wifi_status(self) -> dict[str, Any]:
        """Get WiFi status."""
        try:
            async with self.session.get(
                f"{self.base_url}/wifi/client/status",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.debug("Error fetching WiFi status: %s", err)
            return {}

    async def async_get_global_uptime(self) -> dict[str, Any]:
        """Get device uptime."""
        try:
            async with self.session.get(
                f"{self.base_url}/global/uptime",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.debug("Error fetching uptime: %s", err)
            return {}

    async def async_get_decision_room(self) -> dict[str, Any]:
        """Get room decision data."""
        try:
            async with self.session.get(
                f"{self.base_url}/decision/room",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.debug("Error fetching room decision: %s", err)
            return {}

    async def async_get_decision_silent(self) -> dict[str, Any]:
        """Get silent mode decision data."""
        try:
            async with self.session.get(
                f"{self.base_url}/decision/silent",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.debug("Error fetching silent decision: %s", err)
            return {}

    async def async_get_decision_breeze(self) -> dict[str, Any]:
        """Get breeze mode decision data."""
        try:
            async with self.session.get(
                f"{self.base_url}/decision/breeze",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.debug("Error fetching breeze decision: %s", err)
            return {}
