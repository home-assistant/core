"""Coordinator for Brother integration."""

from asyncio import timeout
import logging

from brother import Brother, BrotherSensors, SnmpError, UnsupportedModelError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type BrotherConfigEntry = ConfigEntry[BrotherDataUpdateCoordinator]


class BrotherDataUpdateCoordinator(DataUpdateCoordinator[BrotherSensors]):
    """Class to manage fetching Brother data from the printer."""

    config_entry: BrotherConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: BrotherConfigEntry, brother: Brother
    ) -> None:
        """Initialize."""
        self.brother = brother

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> BrotherSensors:
        """Update data via library."""
        try:
            async with timeout(20):
                data = await self.brother.async_update()
        except (ConnectionError, SnmpError, UnsupportedModelError) as error:
            raise UpdateFailed(error) from error
        return data
