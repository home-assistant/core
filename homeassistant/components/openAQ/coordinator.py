"""DataUpdateCoordinator for OpenAQ."""
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .aq_client import AQClient

# Define the update interval for fetching data (e.g., 5 minutes)
SCAN_INTERVAL = timedelta(seconds=10)
_LOGGER = logging.getLogger(__name__)


class OpenAQDataCoordinator(DataUpdateCoordinator):
    """Data coordinator for OpenAQ integration."""

    def __init__(self, hass: HomeAssistant, api_key, location_id) -> None:
        """Initialize OpenAQDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="openaq_data",
            update_interval=SCAN_INTERVAL,
        )
        self.api_key = api_key
        self.location_id = location_id
        self.client = AQClient(
            hass=hass,
            api_key=api_key,
            location_id=location_id,
        )

    async def _async_update_data(self):
        """Fetch data from AQClient and update."""
        # _LOGGER.debug("Updating OpenAQ data")
        # datetime.utcnow() - SCAN_INTERVAL
        # data = self.client.get_metrices(prev_fetch_date=prev_fetch)
        device = self.client.get_device()
        data = [sensor.parameter for sensor in device.sensors]
        data.append(device.datetime_last)
        # print("Updated")
        return data

    def get_sensors(self):
        """Get all available sensors."""
        return self.client.sensors
