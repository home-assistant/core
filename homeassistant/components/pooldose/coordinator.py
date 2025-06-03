"""Pooldose API Coordinator."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class PooldoseCoordinator(DataUpdateCoordinator):
    """Coordinator for Pooldose API."""

    def __init__(self, hass: HomeAssistant, api, update_interval) -> None:
        """Initialize the Pooldose coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="pooldose",
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from the Pooldose API."""
        return await self.api.get_instant_values()
