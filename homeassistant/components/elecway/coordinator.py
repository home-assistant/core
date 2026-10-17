"""Expose local storage push updates to Home Assistant."""

from typing import override

from aioelecway import ElecwayError, StorageClient, StorageData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type ElecwayConfigEntry = ConfigEntry[ElecwayCoordinator]


class ElecwayCoordinator(DataUpdateCoordinator[StorageData]):
    """Manage a storage telemetry subscription."""

    def __init__(
        self, hass: HomeAssistant, entry: ElecwayConfigEntry, client: StorageClient
    ) -> None:
        """Initialize a push-only coordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry)
        self.client = client

    @override
    async def _async_update_data(self) -> StorageData:
        """Validate the device before setting up entities."""
        try:
            return await self.client.connect()
        except ElecwayError as err:
            raise UpdateFailed("Unable to receive storage telemetry") from err

    async def async_listen(self) -> None:
        """Mark entities unavailable until valid telemetry resumes."""
        async for data in self.client.updates():
            if data is None:
                self.async_set_update_error(
                    UpdateFailed("Storage telemetry unavailable")
                )
            else:
                self.async_set_updated_data(data)
