"""aq_client for OpenAQ."""
from datetime import timedelta, datetime
import logging

import openaq

_LOGGER = logging.getLogger(__name__)


class AQClient:
    """AQClient class for OpenAQ integration."""

    def __init__(self, api_key, location_id, setup_device=True, hass = None):
        """Initialize AQClient."""
        self.api_key = api_key
        self.location_id = location_id
        self.client = openaq.OpenAQ(api_key=self.api_key)

        if setup_device:
            self.setup_device()

    def setup_device(self):
        """Set sensors and metrices"""
        device = self.get_device()
        self.sensors = device.sensors
        #Get metrices from last 24h
        res = self.get_history()
        return res

    def get_device(self):
        """Get device by id"""

        response = self.client.locations.get(self.location_id)

        if len(response.results) == 1:
            return response.results[0]
        else:
            _LOGGER.debug("Locations API error: %s", response[1])
        return None

    def get_history(self):
        """Get the last 24 hours of metrices"""
        res = self.client.measurements.list(locations_id=self.location_id, date_from=datetime.utcnow() - timedelta(hours=24))
        return res.results[0]

    def get_metrices(self, prev_fetch_date):
        """Get latest measurements"""

        response = self.client.measurements.list(locations_id=self.location_id, page=1, limit=len(self.sensors), date_from=prev_fetch_date)
        return response


#def api_test():
# """Test API functionality."""
# print("RUNNING SCRIPT!")
# client = AQClient('0ce03655421037c966e7f831503000dc93c80a8fc14a434c6406f0adbbfaa61e', 10496)
# data = client.get_device()
# print(data)
 #client.get_hist_data(datetime.datetime(2023, 11, 12), datetime.datetime.now())
# Running the test

# api_test()
