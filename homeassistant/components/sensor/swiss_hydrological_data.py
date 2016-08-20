"""
Support for hydrological data from the Federal Office for the Environment FOEN.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_hydrological_data/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import requests

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (TEMP_CELSIUS, CONF_NAME, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['xmltodict==0.10.2']

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://www.hydrodata.ch/xml/SMS.xml'

CONF_STATION = 'station'
DEFAULT_NAME = 'Water temperature'
ICON = 'mdi:cup-water'

ATTR_LOCATION = 'Location'
ATTR_UPDATE = 'Update'
ATTR_DISCHARGE = 'Discharge'
ATTR_WATERLEVEL = 'Level'
ATTR_DISCHARGE_MEAN = 'Discharge mean'
ATTR_WATERLEVEL_MEAN = 'Level mean'
ATTR_TEMPERATURE_MEAN = 'Temperature mean'
ATTR_DISCHARGE_MAX = 'Discharge max'
ATTR_WATERLEVEL_MAX = 'Level max'
ATTR_TEMPERATURE_MAX = 'Temperature max'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): vol.Coerce(int),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Swiss hydrological sensor."""
    import xmltodict

    name = config.get(CONF_NAME)
    station = config.get(CONF_STATION)

    try:
        response = requests.get(_RESOURCE, timeout=5)
        if any(str(station) == location.get('@StrNr') for location in
               xmltodict.parse(response.text)['AKT_Data']['MesPar']) is False:
            _LOGGER.error('The given station does not exist: %s', station)
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
        if self._state is not STATE_UNKNOWN:
            return self._unit_of_measurement
        else:
            return None

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            return round(float(self._state), 1)
        except ValueError:
            return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        if self.data.measurings is not None:
            if '02' in self.data.measurings:
                attributes[ATTR_WATERLEVEL] = self.data.measurings['02'][
                    'current']
                attributes[ATTR_WATERLEVEL_MEAN] = self.data.measurings['02'][
                    'mean']
                attributes[ATTR_WATERLEVEL_MAX] = self.data.measurings['02'][
                    'max']
            if '03' in self.data.measurings:
                attributes[ATTR_TEMPERATURE_MEAN] = self.data.measurings['03'][
                    'mean']
                attributes[ATTR_TEMPERATURE_MAX] = self.data.measurings['03'][
                    'max']
            if '10' in self.data.measurings:
                attributes[ATTR_DISCHARGE] = self.data.measurings['10'][
                    'current']
                attributes[ATTR_DISCHARGE_MEAN] = self.data.measurings['10'][
                    'current']
                attributes[ATTR_DISCHARGE_MAX] = self.data.measurings['10'][
                    'max']

            attributes[ATTR_LOCATION] = self.data.measurings['location']
            attributes[ATTR_UPDATE] = self.data.measurings['update_time']
            return attributes

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data and update the states."""
        self.data.update()
        if self.data.measurings is not None:
            if '03' not in self.data.measurings:
                self._state = STATE_UNKNOWN
            else:
                self._state = self.data.measurings['03']['current']


# pylint: disable=too-few-public-methods
class HydrologicalData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, station):
        """Initialize the data object."""
        self.station = station
        self.measurings = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from hydrodata.ch."""
        import xmltodict

        details = {}
        try:
            response = requests.get(_RESOURCE, timeout=5)
        except requests.exceptions.ConnectionError:
            _LOGGER.error('Unable to retrieve data from %s', _RESOURCE)

        try:
            stations = xmltodict.parse(response.text)['AKT_Data']['MesPar']
            # Water level: Typ="02", temperature: Typ="03", discharge: Typ="10"
            for station in stations:
                if str(self.station) != station.get('@StrNr'):
                    continue
                for data in ['02', '03', '10']:
                    if data != station.get('@Typ'):
                        continue
                    values = station.get('Wert')
                    if values is not None:
                        details[data] = {
                            'current': values[0],
                            'max': list(values[4].items())[1][1],
                            'mean': list(values[3].items())[1][1]}

                    details['location'] = station.get('Name')
                    details['update_time'] = station.get('Zeit')

            self.measurings = details
        except AttributeError:
            self.measurings = None
