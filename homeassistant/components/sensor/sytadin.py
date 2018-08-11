"""
Support for Sytadin Traffic, French Traffic Supervision.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sytadin/
"""
import logging
import re
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    LENGTH_KILOMETERS, CONF_MONITORED_CONDITIONS, CONF_NAME, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['beautifulsoup4==4.6.1']

_LOGGER = logging.getLogger(__name__)

URL = 'http://www.sytadin.fr/sys/barometres_de_la_circulation.jsp.html'

CONF_ATTRIBUTION = "Data provided by Direction des routes Île-de-France" \
                   "(DiRIF)"

DEFAULT_NAME = 'Sytadin'
REGEX = r'(\d*\.\d+|\d+)'

OPTION_TRAFFIC_JAM = 'traffic_jam'
OPTION_MEAN_VELOCITY = 'mean_velocity'
OPTION_CONGESTION = 'congestion'

SENSOR_TYPES = {
    OPTION_CONGESTION: ['Congestion', ''],
    OPTION_MEAN_VELOCITY: ['Mean Velocity', LENGTH_KILOMETERS+'/h'],
    OPTION_TRAFFIC_JAM: ['Traffic Jam', LENGTH_KILOMETERS],
}

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[OPTION_TRAFFIC_JAM]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of the Sytadin Traffic sensor platform."""
    name = config.get(CONF_NAME)

    sytadin = SytadinData(URL)

    dev = []
    for option in config.get(CONF_MONITORED_CONDITIONS):
        _LOGGER.debug("Sensor device - %s", option)
        dev.append(SytadinSensor(
            sytadin, name, option, SENSOR_TYPES[option][0],
            SENSOR_TYPES[option][1]))
    add_devices(dev, True)


class SytadinSensor(Entity):
    """Representation of a Sytadin Sensor."""

    def __init__(self, data, name, sensor_type, option, unit):
        """Initialize the sensor."""
        self.data = data
        self._state = None
        self._name = name
        self._option = option
        self._type = sensor_type
        self._unit = unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, self._option)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    def update(self):
        """Fetch new state data for the sensor."""
        self.data.update()

        if self.data is None:
            return

        if self._type == OPTION_TRAFFIC_JAM:
            self._state = self.data.traffic_jam
        elif self._type == OPTION_MEAN_VELOCITY:
            self._state = self.data.mean_velocity
        elif self._type == OPTION_CONGESTION:
            self._state = self.data.congestion


class SytadinData:
    """The class for handling the data retrieval."""

    def __init__(self, resource):
        """Initialize the data object."""
        self._resource = resource
        self.data = None
        self.traffic_jam = self.mean_velocity = self.congestion = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Sytadin."""
        from bs4 import BeautifulSoup

        try:
            raw_html = requests.get(self._resource, timeout=10).text
            data = BeautifulSoup(raw_html, 'html.parser')

            values = data.select('.barometre_valeur')
            self.traffic_jam = re.search(REGEX, values[0].text).group()
            self.mean_velocity = re.search(REGEX, values[1].text).group()
            self.congestion = re.search(REGEX, values[2].text).group()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Connection error")
            self.data = None
