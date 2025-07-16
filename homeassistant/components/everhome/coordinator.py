"""Data update coordinator for the EcoTracker integration."""

from datetime import timedelta
import logging

from ecotracker import EcoTracker
from ecotracker.data import EcoTrackerData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type EcoTrackerConfigEntry = ConfigEntry[EcoTrackerDataUpdateCoordinator]


class EcoTrackerDataUpdateCoordinator(DataUpdateCoordinator[EcoTrackerData]):
    """Class to manage fetching EcoTracker data."""

    config_entry: EcoTrackerConfigEntry
    client: EcoTracker
    serial: str = ""
    firmware: str = ""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: EcoTracker,
        host: str,
        config_entry: EcoTrackerConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.client = client
        self.host = host

    async def async_setup(self) -> None:
        """Set up the device coordinator."""
        if not await self.client.async_update():
            raise ConfigEntryNotReady("Connection failed: not ready")

    async def _async_update_data(self) -> EcoTrackerData:
        """Fetch data from the EcoTracker device."""
        if await self.client.async_update():
            data = self.client.get_data()
            self.serial = data.serial
            self.firmware = data.firmware_version
            return data
        raise UpdateFailed("Failed to update EcoTracker data")
