"""
Support for aurora forecast data sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.aurora/
"""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.binary_sensor \
    import (BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

CONF_THRESHOLD = "forecast_threshold"

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Aurora Visibility'
DEFAULT_DEVICE_CLASS = "visible"
DEFAULT_THRESHOLD = 75

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_THRESHOLD, default=DEFAULT_THRESHOLD): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the aurora sensor."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Lat. or long. not set in Home Assistant config")
        return False

    name = config.get(CONF_NAME)
    threshold = config.get(CONF_THRESHOLD)

    try:
        aurora_data = AuroraData(
            hass.config.latitude,
            hass.config.longitude,
            threshold
        )
        aurora_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(
            "Connection to aurora forecast service failed: %s", error)
        return False

    add_devices([AuroraSensor(aurora_data, name)], True)


class AuroraSensor(BinarySensorDevice):
    """Implementation of an aurora sensor."""

    def __init__(self, aurora_data, name):
        """Initialize the sensor."""
        self.aurora_data = aurora_data
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{}'.format(self._name)

    @property
    def is_on(self):
        """Return true if aurora is visible."""
        return self.aurora_data.is_visible if self.aurora_data else False

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEFAULT_DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        if self.aurora_data:
            attrs["visibility_level"] = self.aurora_data.visibility_level
            attrs["message"] = self.aurora_data.is_visible_text

        return attrs

    def update(self):
        """Get the latest data from Aurora API and updates the states."""
        self.aurora_data.update()


class AuroraData(object):
    """Get aurora forecast."""

    def __init__(self, latitude, longitude, threshold):
        """Initialize the data object."""
        self.latitude = latitude
        self.longitude = longitude
        self.number_of_latitude_intervals = 513
        self.number_of_longitude_intervals = 1024
        self.api_url = \
            "http://services.swpc.noaa.gov/text/aurora-nowcast-map.txt"
        self.headers = {"User-Agent": "Home Assistant Aurora Tracker v.0.1.0"}

        self.threshold = int(threshold)
        self.is_visible = None
        self.is_visible_text = None
        self.visibility_level = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Aurora service."""
        try:
            self.visibility_level = self.get_aurora_forecast()
            if int(self.visibility_level) > self.threshold:
                self.is_visible = True
                self.is_visible_text = "visible!"
            else:
                self.is_visible = False
                self.is_visible_text = "nothing's out"

        except requests.exceptions.HTTPError as error:
            _LOGGER.error(
                "Connection to aurora forecast service failed: %s", error)
            return False

    def get_aurora_forecast(self):
        """Get forecast data and parse for given long/lat."""
        raw_data = requests.get(self.api_url, headers=self.headers).text
        forecast_table = [
            row.strip(" ").split("   ")
            for row in raw_data.split("\n")
            if not row.startswith("#")
        ]

        # convert lat and long for data points in table
        converted_latitude = round((self.latitude / 180)
                                   * self.number_of_latitude_intervals)
        converted_longitude = round((self.longitude / 360)
                                    * self.number_of_longitude_intervals)

        return forecast_table[converted_latitude][converted_longitude]
