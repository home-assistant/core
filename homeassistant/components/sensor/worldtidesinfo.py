"""
Support for retrieving tide levels from worldtides.info.

configuration.yaml

sensor:
  - platform: worldtidesinfo
    api_key: "YOUR API KEY"
    latitude: "LATITUDE OF BEACH"
    longitude: "LONGITUDE OF BEACH"
"""
import logging
import time
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE,
                                 CONF_NAME)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'WorldTidesInfo'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3600)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_LATITUDE): cv.latitude,
    vol.Required(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the WorldTidesInfo sensor."""
    data = WorldTidesInfoData(hass)
    name = config.get(CONF_NAME)

    global _RESOURCE
    global LAT
    global LON
    global KEY

    LAT = config.get(CONF_LATITUDE)
    LON = config.get(CONF_LONGITUDE)
    KEY = config.get(CONF_API_KEY)

    STARTTIME = int(time.time())
    _RESOURCE = 'https://www.worldtides.info/api?extremes&length=86400&start' \
                '=%s&lat=%s&lon=%s&key=%s' % (
                    STARTTIME, LAT, LON, KEY)

    try:
        data.update()
    except RunTimeError:
        _LOGGER.error("Unable to connect fetch WorldTidesInfo data: %s")
        return False

    add_devices([WorldTidesInfoSensor(data, name)])
    return True


class WorldTidesInfoSensor(Entity):
    """Representation of a WorldTidesInfo sensor."""

    def __init__(self, data, name):
        """Initialize a WorldTidesInfo sensor."""
        self.data = data
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self.data.data:
            if "High" in str(self.data.data['extremes'][0]['type']):
                tidetime = time.strftime('%I:%M %p', time.localtime(
                    self.data.data['extremes'][0]['dt']))
                return "High tide at %s" % (tidetime)
            elif "Low" in str(self.data.data['extremes'][0]['type']):
                tidetime = time.strftime('%I:%M %p', time.localtime(
                    self.data.data['extremes'][1]['dt']))
                return "Low tide at %s" % (tidetime)
            else:
                return STATE_UNKNOWN
        else:
            return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {}
        if "High" in str(self.data.data['extremes'][0]['type']):
            attr['high_tide_time_utc'] = self.data.data['extremes'][0]['date']
            attr['high_tide_height'] = self.data.data['extremes'][0]['height']
            attr['low_tide_time_utc'] = self.data.data['extremes'][1]['date']
            attr['low_tide_height'] = self.data.data['extremes'][1]['height']
        elif "Low" in str(self.data.data['extremes'][0]['type']):
            attr['high_tide_time_utc'] = self.data.data['extremes'][1]['date']
            attr['high_tide_height'] = self.data.data['extremes'][1]['height']
            attr['low_tide_time_utc'] = self.data.data['extremes'][0]['date']
            attr['low_tide_height'] = self.data.data['extremes'][0]['height']
        return attr

    def update(self):
        """Update current values."""
        self.data.update()


class WorldTidesInfoData(object):
    """Get data from WorldTidesInfo API."""

    def __init__(self, hass):
        """Initialize the data object."""
        self._hass = hass
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from WorldTidesInfo API."""
        STARTTIME = int(time.time())
        _RESOURCE = 'https://www.worldtides.info/api?extremes&length=86400' \
                    '&start=%s&lat=%s&lon=%s&key=%s' % (
                        STARTTIME, LAT, LON, KEY)

        try:
            self.data = requests.get(_RESOURCE, timeout=10).json()
            _LOGGER.debug("Data = %s", self.data)
            _LOGGER.debug("Tide data queried with start time set to: %s",
                          (STARTTIME))
        except ValueError as err:
            _LOGGER.error("Check WorldTidesInfo %s", err.args)
            self.data = None
            raise
