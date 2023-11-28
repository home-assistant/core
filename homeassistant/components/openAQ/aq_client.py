"""aq_client for OpenAQ."""
from datetime import datetime, timedelta
import logging

import openaq

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class AQClient:
    """AQClient class for OpenAQ integration."""

    def __init__(
        self, api_key, location_id, setup_device=True, hass: HomeAssistant | None = None
    ) -> None:
        """Initialize AQClient."""
        self.time = datetime.now() - timedelta(hours=24)
        self.api_key = api_key
        self.location_id = location_id
        self.client = openaq.OpenAQ(api_key=self.api_key)

        if setup_device:
            self.setup_device()

    def setup_device(self):
        """Set sensors and metrices."""
        device = self.get_device()
        self.sensors = device.sensors
        self.last_updated = device.datetime_last

    def get_device(self):
        """Get device by id."""
        response = self.client.locations.get(self.location_id)

        if len(response.results) == 1:
            return response.results[0]
        _LOGGER.debug("Locations API error: %s", response[1])
        return None

    def get_history(self):
        """Get the last 24 hours of metrices."""
        response = self.client.measurements.list(
            locations_id=self.location_id,
            date_from=datetime.now() - timedelta(hours=24),
        )
        return response.results[0]

    def get_latest_metrices(self):
        """Get latest measurements."""

        response = self.client.measurements.list(
            locations_id=self.location_id,
            page=1,
            limit=len(self.sensors),
            date_from=self.time,
        )
        self.time = datetime.now()
        return response
