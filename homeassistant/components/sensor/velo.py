"""
Support for Velo Antwerpen.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.velo/
"""

import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Velo'
DEFAULT_ICON = 'mdi:bike'
DEFAULT_UNIT = 'bikes'

CONF_STATION_ID = 'station_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Velo sensor."""
    name = config.get(CONF_NAME)
    station = config.get(CONF_STATION_ID)

    add_entities([VeloSensor(name, station)], True)

class VeloSensor(Entity):
    def __init__(self, name, station):
        self._name = name
        self._station = station
        self._state = None
        self._station_data = self.make_request()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return DEFAULT_UNIT

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return DEFAULT_ICON

    @property
    def station(self):
        """Return the station id"""
        return self._station

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            "Station ID": self._station,
            "Station": self._station_data["address"],
            "Data provided by": "https://www.velo-antwerpen.be/",
        }

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def make_request(self):
        """Perform the API request to the Velo Antwerpen API"""
        request = requests.Request("GET", "https://www.velo-antwerpen.be/availability_map/getJsonObject"
            ).prepare()
        try:
            with requests.Session() as sess:
                response = sess.send(request, timeout=10)

            station_data = response.json()
            result = list(filter(lambda x: (x['id'] == self._station), station_data))
            return result[0]
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s from %s failed with %s",
                          request, request.url, ex)

    def update(self):
        try:
            station_data = self.make_request()
            self._state = int(station_data["bikes"])
        except:
            self._state = None
