"""Pooldose API Coordinator."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


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
        try:
            return await self.api.get_instant_values()
        except Exception as err:
            _LOGGER.warning(
                "Pooldose update failed, entities will be unavailable: %s", err
            )
            raise UpdateFailed from err

    @property
    def available(self) -> bool:
        """Return True if coordinator is available."""
        return self.last_update_success
