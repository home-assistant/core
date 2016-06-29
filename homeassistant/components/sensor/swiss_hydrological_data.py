"""
Support for hydrological data from the Federal Office for the Environment FOEN.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_hydrological_data/
"""
import logging
import collections
from datetime import timedelta

import voluptuous as vol
import requests

from homeassistant.const import (TEMP_CELSIUS, CONF_PLATFORM, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['beautifulsoup4==4.4.1']

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://www.hydrodaten.admin.ch/en/'

DEFAULT_NAME = 'Water temperature'
CONF_STATION = 'station'
ICON = 'mdi:cup-water'

ATTR_DISCHARGE = 'Discharge'
ATTR_WATERLEVEL = 'Level'
ATTR_DISCHARGE_MEAN = 'Discharge mean'
ATTR_WATERLEVEL_MEAN = 'Level mean'
ATTR_TEMPERATURE_MEAN = 'Temperature mean'
ATTR_DISCHARGE_MAX = 'Discharge max'
ATTR_WATERLEVEL_MAX = 'Level max'
ATTR_TEMPERATURE_MAX = 'Temperature max'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'swiss_hydrological_data',
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_STATION): cv.string,
})

HydroData = collections.namedtuple(
    "HydrologicalData",
    ['discharge', 'waterlevel', 'temperature', 'discharge_mean',
     'waterlevel_mean', 'temperature_mean', 'discharge_max', 'waterlevel_max',
     'temperature_max'])

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Swiss hydrological sensor."""
    station = config.get(CONF_STATION)
    name = config.get(CONF_NAME, DEFAULT_NAME)

    try:
        response = requests.get('{}/{}.html'.format(_RESOURCE, station),
                                timeout=5)
        if not response.ok:
            _LOGGER.error('The given station does not seem to exist: %s',
                          station)
            return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error('The URL is not accessible')
        return False

    data = HydrologicalData(station)
    add_devices([SwissHydrologicalDataSensor(name, data)])


# pylint: disable=too-few-public-methods
class SwissHydrologicalDataSensor(Entity):
    """Implementation of an Swiss hydrological sensor."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._unit_of_measurement = TEMP_CELSIUS
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.data.measurings is not None:
            return {
                ATTR_DISCHARGE: self.data.measurings.discharge,
                ATTR_WATERLEVEL: self.data.measurings.waterlevel,
                ATTR_DISCHARGE_MEAN: self.data.measurings.discharge_mean,
                ATTR_WATERLEVEL_MEAN: self.data.measurings.waterlevel_mean,
                ATTR_TEMPERATURE_MEAN: self.data.measurings.temperature_mean,
                ATTR_DISCHARGE_MAX: self.data.measurings.discharge_max,
                ATTR_WATERLEVEL_MAX: self.data.measurings.waterlevel_max,
                ATTR_TEMPERATURE_MAX: self.data.measurings.temperature_max,
            }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data and update the states."""
        self.data.update()
        if self.data.measurings is not None:
            self._state = self.data.measurings.temperature


# pylint: disable=too-few-public-methods
class HydrologicalData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, station):
        """Initialize the data object."""
        self.station = station
        self.measurings = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from hydrodaten.admin.ch."""
        from bs4 import BeautifulSoup

        try:
            response = requests.get('{}/{}.html'.format(_RESOURCE,
                                                        self.station),
                                    timeout=5)
        except requests.exceptions.ConnectionError:
            _LOGGER.error('Unable to retrieve data')
            response = None

        try:
            tables = BeautifulSoup(response.content,
                                   'html.parser').findChildren('table')
            rows = tables[0].findChildren(['th', 'tr'])

            details = []

            for row in rows:
                cells = row.findChildren('td')
                for cell in cells:
                    details.append(cell.string)

            self.measurings = HydroData._make(details)
        except AttributeError:
            self.measurings = None
