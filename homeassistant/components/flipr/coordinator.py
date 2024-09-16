"""DataUpdateCoordinator for flipr integration."""

from datetime import timedelta
import logging

from flipr_api import FliprAPIRestClient
from flipr_api.exceptions import FliprError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class FliprDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to hold Flipr data retrieval."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, client: FliprAPIRestClient, flipr_or_hub_id: str
    ) -> None:
        """Initialize."""
        self.device_id = flipr_or_hub_id
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=f"Flipr or Hub data measure for {self.device_id}",
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            data = await self.hass.async_add_executor_job(
                self.client.get_pool_measure_latest, self.device_id
            )
        except FliprError as error:
            raise UpdateFailed(error) from error

        return data
