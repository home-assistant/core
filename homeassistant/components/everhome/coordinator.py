"""Data update coordinator for the EcoTracker integration."""

from datetime import timedelta
import logging

from ecotracker import EcoTracker
from ecotracker.data import EcoTrackerData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
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
        update_interval: timedelta = timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        config_entry: EcoTrackerConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self.host = host
        self.config_entry = config_entry

    async def _async_update_data(self) -> EcoTrackerData:
        """Fetch data from the EcoTracker device."""
        if await self.client.async_update():
            data = self.client.get_data()
            self.serial = data.serial
            newFirmware = data.firmware_version
            if self.firmware and newFirmware != self.firmware:
                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, self.serial)}
                )
                assert device_entry
                device_registry.async_update_device(
                    device_entry.id,
                    sw_version=newFirmware,
                )
            self.firmware = newFirmware
            return data
        raise UpdateFailed("Failed to update EcoTracker data")
