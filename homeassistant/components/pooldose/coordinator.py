"""PoolDose API Coordinator."""

import logging

from pooldose.client import PooldoseClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class PooldoseCoordinator(DataUpdateCoordinator):
    """Coordinator for PoolDose API."""

    def __init__(
        self, hass: HomeAssistant, client: PooldoseClient, update_interval
    ) -> None:
        """Initialize the PoolDose coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name="pooldose",
            update_interval=update_interval,
        )
        self.client = client

    async def _async_update_data(self):
        """Fetch data from the PoolDose API."""
        try:
            return await self.client.instant_values()
        except Exception as err:
            # Raise UpdateFailed so last_update_success is set to False
            raise UpdateFailed(f"Error fetching data: {err}") from err

    @property
    def available(self) -> bool:
        """Return True if coordinator is available."""
        return self.last_update_success
