"""Class representing a Devialet update coordinator."""
from datetime import timedelta
import logging

from devialet import DevialetApi

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


class DevialetCoordinator(DataUpdateCoordinator[None]):
    """Devialet update coordinator."""

    def __init__(self, hass: HomeAssistant, client: DevialetApi) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.client.async_update()
