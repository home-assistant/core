"""aq_client for OpenAQ."""
import datetime
from datetime import timedelta
import logging

import openaq

SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


class AQClient:
    """AQClient class for OpenAQ integration."""

    def __init__(self, api_key, location_id):
        """Initialize AQClient."""
        self.api_key = api_key
        self.location_id = location_id
        self.client = openaq.OpenAQ(api_key=self.api_key)
        self.name = None  # Initialize attributes in __init__
        self.sensors = None
        self.coordinates = None
        self.lastUpdated = None
        self.firstUpdated = None

    def setup_device(self):
        """Set up device information and retrieve the API response."""
        _LOGGER.debug("Setting up device")
        response = self.client.locations.get(self.location_id)
        if response[0] == 200:
            data = response[1]
            if isinstance(data, dict) and data:
                # Check if data is a non-empty dictionary
                # Assuming the necessary keys are present in the dictionary
                self.name = data.get("name")
                self.sensors = data.get("sensors")
                self.coordinates = data.get("coordinates")
                self.lastUpdated = data.get("lastUpdated", {}).get("local")
                self.firstUpdated = data.get("firstUpdated", {}).get("local")
                _LOGGER.debug("Getting last measurements")
                _LOGGER.debug(self.lastUpdated)
                _LOGGER.debug(datetime.datetime.now())
                measurements = self.client.latest(
                    city=self.location_id,
                    date_from=self.lastUpdated,
                    date_to=datetime.datetime.now(),
                )
                if measurements[0] == 200:
                    latest_measurements_data = measurements[1]
                    if latest_measurements_data:
                        _LOGGER.debug(
                            "Latest measurements data: %s", latest_measurements_data
                        )
                        return latest_measurements_data
                    _LOGGER.debug("No measurements found")
                _LOGGER.debug("Measurements API error: %s", measurements[1])
            else:
                _LOGGER.debug("Invalid or empty response")
        else:
            _LOGGER.debug("Locations API error: %s", response[1])
        return None

    def get_hist_data(self, startDate, stopDate):
        """Retrieve historical data."""
        _LOGGER.debug("Getting historical data from device")
        res = self.client.measurements(
            city=self.location_id, date_from=startDate, date_to=stopDate
        )
        if res[0] == 200:
            res_data = res[1]
            if res_data:
                _LOGGER.debug("Historical data: %s", res_data)
                _LOGGER.debug("Successfully got historical data")
            else:
                _LOGGER.debug("No historical data found")
        else:
            _LOGGER.debug("Historical data API error: %s", res[1])

    def get_location(self, locationid):
        """Returns a location"""
        res = self.client.locations(locationid)
        if(res[0] == 200):
            return res[1]
        else:
            _LOGGER.debug("Error getting location: %s", locationid)
            return None

#def api_test():
# """Test API functionality."""
 #print("RUNNING SCRIPT!")
 #client = AQClient('0ce03655421037c966e7f831503000dc93c80a8fc14a434c6406f0adbbfaa61e', 10496)
 #data = client.setup_device()
 #print(data)
 #client.get_hist_data(datetime.datetime(2023, 11, 12), datetime.datetime.now())
# Running the test

#api_test()
