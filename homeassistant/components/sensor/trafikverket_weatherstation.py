"""
Weather information for air and road temperature, provided by Trafikverket.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.trafikverket_weatherstation/
"""
from datetime import timedelta
import json
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_NAME, CONF_TYPE, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by Trafikverket API"

CONF_STATION = 'station'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SCAN_INTERVAL = timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_STATION): cv.string,
    vol.Required(CONF_TYPE): vol.In(['air', 'road']),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Trafikverket sensor platform."""
    sensor_name = config.get(CONF_NAME)
    sensor_api = config.get(CONF_API_KEY)
    sensor_station = config.get(CONF_STATION)
    sensor_type = config.get(CONF_TYPE)

    add_devices([TrafikverketWeatherStation(
        sensor_name, sensor_api, sensor_station, sensor_type)], True)


class TrafikverketWeatherStation(Entity):
    """Representation of a Trafikverket sensor."""

    def __init__(self, sensor_name, sensor_api, sensor_station, sensor_type):
        """Initialize the Trafikverket sensor."""
        self._name = sensor_name
        self._api = sensor_api
        self._station = sensor_station
        self._type = sensor_type
        self._state = None
        self._attributes = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        url = 'http://api.trafikinfo.trafikverket.se/v1.3/data.json'

        if self._type == 'road':
            air_vs_road = 'Road'
        else:
            air_vs_road = 'Air'

        xml = """
        <REQUEST>
              <LOGIN authenticationkey='""" + self._api + """' />
              <QUERY objecttype="WeatherStation">
                    <FILTER>
                          <EQ name="Name" value='""" + self._station + """' />
                    </FILTER>
                    <INCLUDE>Measurement.""" + air_vs_road + """.Temp</INCLUDE>
              </QUERY>
        </REQUEST>"""

        # Testing JSON post request.
        try:
            post = requests.post(url, data=xml.encode('utf-8'), timeout=5)
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Please check network connection: %s", err)
            return

        # Checking JSON respons.
        try:
            data = json.loads(post.text)
            result = data["RESPONSE"]["RESULT"][0]
            final = result["WeatherStation"][0]["Measurement"]
        except KeyError:
            _LOGGER.error("Incorrect weather station or API key")
            return

        # air_vs_road contains "Air" or "Road" depending on user input.
        self._state = final[air_vs_road]["Temp"]
