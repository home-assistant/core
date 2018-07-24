"""
This component provides HA sensor support for the NOAA Tides and Currents API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.noaa_tides/
"""
import logging
import time
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION, CONF_NAME, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

API_URL = 'https://tidesandcurrents.noaa.gov/api/datagetter'
DEFAULT_ATTRIBUTION = "Data provided by NOAA"
DEFAULT_NAME = 'NOAA Tides'
DEFAULT_TZ = 'lst_ldt'

CONF_STA_ID = 'station_id'
CONF_TZ = 'timezone'
CONF_UNITS = 'units'

SCAN_INTERVAL = timedelta(seconds=3600)

TZS = ['gmt', 'lst', 'lst_ldt']
UNITS = ['english', 'metric']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STA_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TZ, default=DEFAULT_TZ): vol.In(TZS),
    vol.Optional(CONF_UNITS): vol.In(UNITS),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the NOAATidesAndCurrents sensor."""
    sta = config[CONF_STA_ID]
    name = config.get(CONF_NAME)
    t_z = config.get(CONF_TZ)

    if CONF_UNITS in config:
        units = config.get(CONF_UNITS)
    elif hass.config.units.is_metric:
        units = UNITS[1]
    else:
        units = UNITS[0]

    add_devices([NOAATidesAndCurrentsSensor(name, sta, t_z, units)], True)


class NOAATidesAndCurrentsSensor(Entity):
    """Representation of a NOAATidesAndCurrents sensor."""

    def __init__(self, name, sta, t_z, units):
        """Initialize the sensor."""
        self._name = name
        self._sta = sta
        self._tz = t_z
        self._units = units
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        predictions = self.data['predictions']
        if "H" in predictions[0]['type']:
            attr['high_tide_time'] = predictions[0]['t']
            attr['high_tide_height'] = predictions[0]['v']
            attr['low_tide_time'] = predictions[1]['t']
            attr['low_tide_height'] = predictions[1]['v']
        elif "L" in predictions[0]['type']:
            attr['high_tide_time'] = predictions[1]['t']
            attr['high_tide_height'] = predictions[1]['v']
            attr['low_tide_time'] = predictions[0]['t']
            attr['low_tide_height'] = predictions[0]['v']
        return attr

    @property
    def state(self):
        """Return the state of the device."""
        if self.data:
            predictions = self.data['predictions']
            api_time = time.strptime(predictions[0]['t'], "%Y-%m-%d %H:%M")
            if "H" in predictions[0]['type']:
                tidetime = time.strftime('%I:%M %p', api_time)
                return "High tide at %s" % (tidetime)
            if "L" in predictions[0]['type']:
                tidetime = time.strftime('%I:%M %p', api_time)
                return "Low tide at %s" % (tidetime)
            return STATE_UNKNOWN
        return STATE_UNKNOWN

    def update(self):
        """Get the latest data from NOAA Tides and Currents API."""
        begin = time.strftime("%Y%m%d %H:%M")
        params = {'station': self._sta,
                  'product': 'predictions',
                  'application': 'HOMEASSISTANT',
                  'begin_date': begin,
                  'range': '72',
                  'datum': 'MLLW',
                  'time_zone': self._tz,
                  'units': self._units,
                  'interval': 'hilo',
                  'format': 'json',
                  }
        try:
            self.data = requests.get(API_URL, params=params, timeout=10).json()
            _LOGGER.debug("Data = %s", self.data)
            _LOGGER.info("Recent Tide data queried with start time set to")
        except ValueError as err:
            _LOGGER.error("Check NOAA Tides and Currents %s", err.args)
            self.data = None
            raise
