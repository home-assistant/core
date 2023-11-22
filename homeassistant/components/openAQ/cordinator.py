"""DataUpdateCoordinator for OpenAQ."""
from datetime import timedelta, datetime
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
        prev_fetch = datetime.utcnow - SCAN_INTERVAL
        data = await self.hass.async_add_executor_job(self.client.get_metrices(prev_fetch_date=prev_fetch))
        return data

