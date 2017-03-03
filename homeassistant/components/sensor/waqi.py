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

REQUIREMENTS = ['pwaqi==3.0']

_LOGGER = logging.getLogger(__name__)

ATTR_DOMINENTPOL = 'dominentpol'
ATTR_HUMIDITY = 'humidity'
ATTR_NITROGEN_DIOXIDE = 'nitrogen_dioxide'
ATTR_OZONE = 'ozone'
ATTR_PM10 = 'pm_10'
ATTR_PM2_5 = 'pm_2_5'
ATTR_PRESSURE = 'pressure'
ATTR_SULFUR_DIOXIDE = 'sulfur_dioxide'
ATTR_TIME = 'time'
ATTRIBUTION = 'Data provided by the World Air Quality Index project'

CONF_LOCATIONS = 'locations'
CONF_STATIONS = 'stations'
CONF_API_TOKEN = 'token'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

SENSOR_TYPES = {
    'aqi': ['AQI', '0-300+', 'mdi:cloud']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_STATIONS): cv.ensure_list,
    vol.Required(CONF_API_TOKEN): cv.string,
    vol.Required(CONF_LOCATIONS): cv.ensure_list,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the requested World Air Quality Index locations."""
    import pwaqi

    dev = []
    token = config.get(CONF_API_TOKEN)
    station_filter = config.get(CONF_STATIONS)
    for location_name in config.get(CONF_LOCATIONS):
        station_ids = pwaqi.findStationCodesByCity(location_name, token)
        _LOGGER.info("The following stations were returned: %s", station_ids)
        for station in station_ids:
            waqi_sensor = WaqiSensor(WaqiData(station, token), station)
            if (not station_filter) or \
               (waqi_sensor.station_name in station_filter):
                dev.append(WaqiSensor(WaqiData(station, token), station))

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
    def station_name(self):
        """Return the name of the station."""
        try:
            return self._details['city']['name']
        except (KeyError, TypeError):
            return None

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
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        attrs = {}

        if self.data is not None:
            try:
                attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
                attrs[ATTR_TIME] = self._details.get('time')
                attrs[ATTR_DOMINENTPOL] = self._details.get('dominentpol')
                for values in self._details['iaqi']:
                    if values['p'] == 'pm25':
                        attrs[ATTR_PM2_5] = values['cur']
                    elif values['p'] == 'pm10':
                        attrs[ATTR_PM10] = values['cur']
                    elif values['p'] == 'h':
                        attrs[ATTR_HUMIDITY] = values['cur']
                    elif values['p'] == 'p':
                        attrs[ATTR_PRESSURE] = values['cur']
                    elif values['p'] == 't':
                        attrs[ATTR_TEMPERATURE] = values['cur']
                    elif values['p'] == 'o3':
                        attrs[ATTR_OZONE] = values['cur']
                    elif values['p'] == 'no2':
                        attrs[ATTR_NITROGEN_DIOXIDE] = values['cur']
                    elif values['p'] == 'so2':
                        attrs[ATTR_SULFUR_DIOXIDE] = values['cur']
                return attrs
            except (IndexError, KeyError):
                return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._details = self.data.data


class WaqiData(object):
    """Get the latest data and update the states."""

    def __init__(self, station_id, token):
        """Initialize the data object."""
        self._station_id = station_id
        self._token = token
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the data from World Air Quality Index and updates the states."""
        import pwaqi
        try:
            self.data = pwaqi.get_station_observation(
                self._station_id, self._token)
        except AttributeError:
            _LOGGER.exception("Unable to fetch data from WAQI")
