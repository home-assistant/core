"""Coordinator for TheSilentWave integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pysilentwave import SilentWaveClient
from pysilentwave.exceptions import SilentWaveError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)

# Type alias for config entry with coordinator
type TheSilentWaveConfigEntry = ConfigEntry[TheSilentWaveCoordinator]


class TheSilentWaveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching the data from the API."""

    config_entry: TheSilentWaveConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TheSilentWaveConfigEntry) -> None:
        """Initialize the coordinator."""
        websession = async_get_clientsession(hass)
        self._device_name = entry.title
        self._host = entry.data["host"]
        self.client = SilentWaveClient(self._host, session=websession)

        super().__init__(
            hass,
            _LOGGER,
            name=self._device_name,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

    @property
    def device_name(self) -> str:
        """Return the name of the device."""
        return self._device_name

    @property
    def host(self) -> str:
        """Return the host address."""
        return self._host

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            status = await self.client.get_status()
        except SilentWaveError as exc:
            raise UpdateFailed("Failed to fetch device status") from exc
        else:
            return {"status": status}
