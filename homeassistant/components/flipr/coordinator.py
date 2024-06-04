"""DataUpdateCoordinator for flipr integration."""

from datetime import timedelta
import logging

from flipr_api import FliprAPIRestClient
from flipr_api.exceptions import FliprError

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_FLIPR_ID

_LOGGER = logging.getLogger(__name__)


class FliprDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to hold Flipr data retrieval."""

    def __init__(self, hass, entry):
        """Initialize."""
        username = entry.data[CONF_EMAIL]
        password = entry.data[CONF_PASSWORD]
        self.flipr_id = entry.data[CONF_FLIPR_ID]

        # Establishes the connection.
        self.client = FliprAPIRestClient(username, password)
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=f"Flipr data measure for {self.flipr_id}",
            update_interval=timedelta(minutes=60),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            data = await self.hass.async_add_executor_job(
                self.client.get_pool_measure_latest, self.flipr_id
            )
        except FliprError as error:
            raise UpdateFailed(error) from error

        return data
