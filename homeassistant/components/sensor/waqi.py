"""
Support for the World Air Quality Index service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.waqi/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_TEMPERATURE, STATE_UNKNOWN)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pwaqi==1.3']

_LOGGER = logging.getLogger(__name__)

ATTR_DOMINENTPOL = 'dominentpol'
ATTR_HUMIDITY = 'humidity'
ATTR_NITROGEN_DIOXIDE = 'nitrogen_dioxide'
ATTR_OZONE = 'ozone'
ATTR_PARTICLE = 'particle'
ATTR_PRESSURE = 'pressure'
ATTR_TIME = 'time'
ATTRIBUTION = 'Data provided by the World Air Quality Index project'

CONF_LOCATIONS = 'locations'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

SENSOR_TYPES = {
    'aqi': ['AQI', '0-300+', 'mdi:cloud']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATIONS): cv.ensure_list
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the requested World Air Quality Index locations."""
    import pwaqi

    dev = []
    for location_name in config.get(CONF_LOCATIONS):
        station_ids = pwaqi.findStationCodesByCity(location_name)
        _LOGGER.error('The following stations were returned: %s', station_ids)
        for station in station_ids:
            dev.append(WaqiSensor(WaqiData(station), station))

    add_devices(dev)


class WaqiSensor(Entity):
    """Implementation of a WAQI sensor."""

    def __init__(self, data, station_id):
        """Initialize the sensor."""
        self.data = data
        self._station_id = station_id
        self._details = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        try:
            return 'WAQI {}'.format(self._details['city']['name'])
        except (KeyError, TypeError):
            return 'WAQI {}'.format(self._station_id)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:cloud'

    @property
    def state(self):
        """Return the state of the device."""
        if self._details is not None:
            return self._details.get('aqi')
        else:
            return STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'AQI'

    @property
    def state_attributes(self):
        """Return the state attributes of the last update."""
        try:
            return {
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_TIME: self._details.get('time'),
                ATTR_HUMIDITY: self._details['iaqi'][5]['cur'],
                ATTR_PRESSURE: self._details['iaqi'][4]['cur'],
                ATTR_TEMPERATURE: self._details['iaqi'][3]['cur'],
                ATTR_OZONE: self._details['iaqi'][1]['cur'],
                ATTR_PARTICLE: self._details['iaqi'][0]['cur'],
                ATTR_NITROGEN_DIOXIDE: self._details['iaqi'][2]['cur'],
                ATTR_DOMINENTPOL: self._details.get('dominentpol'),
            }
        except (IndexError, KeyError):
            return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._details = self.data.data


class WaqiData(object):
    """Get the latest data and update the states."""

    def __init__(self, station_id):
        """Initialize the data object."""
        self._station_id = station_id
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the data from World Air Quality Index and updates the states."""
        import pwaqi
        try:
            self.data = pwaqi.getStationObservation(self._station_id)
        except AttributeError:
            _LOGGER.exception("Unable to fetch data from WAQI")
