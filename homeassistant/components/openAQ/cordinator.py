"""DataUpdateCoordinator for OpenAQ."""
from datetime import timedelta
import logging

from aq_client import AQClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# Define the update interval for fetching data (e.g., 5 minutes)
SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


class OpenAQDataCoordinator(DataUpdateCoordinator):
    """Data coordinator for OpenAQ integration."""

    def __init__(self, hass, api_key, location_id):
        """Initialize OpenAQDataCoordinator."""
        self.api_key = api_key
        self.location_id = location_id
        self.data = {}
        self.client = AQClient(
            hass=hass,
            api_key=api_key,
            location_id=location_id,
        )
        super().__init__(
            hass,
            _LOGGER,
            name="openaq_data",
            update_interval=SCAN_INTERVAL,
            update_method=self._async_update_data,
        )

    async def async_update(self):
        """Fetch data from AQClient and update."""
        _LOGGER.debug("Updating OpenAQ data")
        self.data = await self.hass.async_add_executor_job(self.client.setup_device)
        return self.data

    async def async_fetch_hist_data(self, start_date, stop_date):
        """Fetch historical data from AQClient."""
        _LOGGER.debug("Fetching historical data")
        await self.hass.async_add_executor_job(
            self.client.get_hist_data, start_date, stop_date
        )
