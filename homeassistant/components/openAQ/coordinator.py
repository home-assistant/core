"""DataUpdateCoordinator for OpenAQ."""
import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .aq_client import AQClient
from .const import DOMAIN

# Define the update interval for fetching data (e.g., 5 minutes)
SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


class OpenAQDataCoordinator(DataUpdateCoordinator):
    """Data coordinator for OpenAQ integration."""

    def __init__(self, hass: HomeAssistant, api_key, location_id) -> None:
        """Initialize OpenAQDataCoordinator."""
        self.api_key = api_key
        self.location_id = location_id
        self.sensor_data = {}
        self.client = AQClient(
            hass=hass,
            api_key=api_key,
            location_id=location_id,
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from AQClient and update."""
        async with asyncio.timeout(10):
            metrics = self.client.get_latest_metrices().results
            for metric in metrics:
                self.sensor_data[metric.parameter.name] = metric.value
                print(str(metric.parameter.name) + " " + str(metric.value))
            last_update = self.client.get_device().datetime_last.utc
            if last_update:
                self.sensor_data["last_update"] = last_update
            print("updated " + str(self.sensor_data))
            self.data = self.sensor_data
            return self.sensor_data

    def get_sensors(self):
        """Get all available sensors."""
        return self.client.sensors
