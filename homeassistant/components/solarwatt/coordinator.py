"""DataUpdateCoordinator for Solarwatt integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp.client_exceptions import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_PATH, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=5)


class SolarwattDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch data from the Solarwatt device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry

        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data.get(CONF_PORT, DEFAULT_PORT)

        scheme = "http"
        self._base_url = f"{scheme}://{self._host}:{self._port}"

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({self._host}:{self._port})",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Solarwatt DEVICE API."""
        session = async_get_clientsession(self.hass)
        url = f"{self._base_url}{API_PATH}"

        _LOGGER.debug("Requesting Solarwatt data from %s", url)

        try:
            # Ruff SIM117: use a single with with multiple contexts
            async with asyncio.timeout(10), session.get(url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise UpdateFailed(
                        f"Error response from Solarwatt API: {resp.status} - {text}"
                    )

                data: dict[str, Any] = await resp.json()

        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(
                f"Error communicating with Solarwatt device: {err}"
            ) from err
        except ValueError as err:
            # JSON decode error
            raise UpdateFailed(f"Invalid JSON from Solarwatt device: {err}") from err

        _LOGGER.debug("Received Solarwatt data: %s", str(data)[:500])
        return data
