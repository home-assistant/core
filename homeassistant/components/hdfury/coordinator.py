"""DataUpdateCoordinators for HDFury Integration."""

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import Final

from hdfury import HDFuryAPI, HDFuryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_INFO: Final = timedelta(seconds=60)
SCAN_INTERVAL_CONFIG: Final = timedelta(seconds=60)


class HDFuryDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Base coordinator for HDFury devices."""

    _update_interval: timedelta
    _coordinator_name: str

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: HDFuryAPI
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"HDFury {self._coordinator_name}",
            update_interval=self._update_interval,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from the device."""
        try:
            return await self._internal_update_data()
        except HDFuryError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

    @abstractmethod
    async def _internal_update_data(self) -> dict[str, str]:
        """Update coordinator data."""


class HDFuryInfoCoordinator(HDFuryDataUpdateCoordinator):
    """Coordinator for HDFury device info (signal routing, port selections)."""

    _update_interval = SCAN_INTERVAL_INFO
    _coordinator_name = "Info"

    async def _internal_update_data(self) -> dict[str, str]:
        """Fetch device info."""
        return await self.client.get_info()


class HDFuryConfigCoordinator(HDFuryDataUpdateCoordinator):
    """Coordinator for HDFury device config (switches, numbers)."""

    _update_interval = SCAN_INTERVAL_CONFIG
    _coordinator_name = "Config"

    async def _internal_update_data(self) -> dict[str, str]:
        """Fetch device configuration."""
        return await self.client.get_config()
