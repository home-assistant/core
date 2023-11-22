"""DataUpdateCoordinator for OpenAQ."""
from datetime import datetime, timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .aq_client import AQClient

# Define the update interval for fetching data (e.g., 5 minutes)
SCAN_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)


class OpenAQDataCoordinator(DataUpdateCoordinator):
    """Data coordinator for OpenAQ integration."""

    def __init__(self, hass, api_key, location_id):
        """Initialize OpenAQDataCoordinator."""
        print("INIT COORDINATOR")
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
            update_method=self.async_update,
        )

    async def async_update(self):
        """Fetch data from AQClient and update."""
        _LOGGER.debug("Updating OpenAQ data")
        datetime.utcnow() - SCAN_INTERVAL
        # data = self.client.get_metrices(prev_fetch_date=prev_fetch)
        device = self.client.get_device()
        data = [sensor.parameter for sensor in device.sensors]
        print("I WAS CALLED")
        print(data)
        print("I WAS CALLED")
        return data

    def get_sensors(self):
        return self.client.sensors
