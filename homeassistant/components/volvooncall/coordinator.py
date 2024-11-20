"""Support for Volvo On Call."""

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UPDATE_INTERVAL
from .models import VolvoData

_LOGGER = logging.getLogger(__name__)


class VolvoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Volvo coordinator."""

    def __init__(self, hass: HomeAssistant, volvo_data: VolvoData) -> None:
        """Initialize the data update coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name="volvooncall",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

        self.volvo_data = volvo_data

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        async with asyncio.timeout(10):
            await self.volvo_data.update()
