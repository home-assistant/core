"""Support for Volvo On Call."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UPDATE_INTERVAL
from .models import VolvoData

_LOGGER = logging.getLogger(__name__)


class VolvoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Volvo coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, volvo_data: VolvoData
    ) -> None:
        """Initialize the data update coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="volvooncall",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

        self.volvo_data = volvo_data

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        async with asyncio.timeout(10):
            await self.volvo_data.update()
