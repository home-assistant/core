"""
This component provides HA sensor support for the worldtides.info API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.worldtidesinfo/
"""
import logging
import time
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE,
                                 CONF_NAME, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'WorldTidesInfo'

SCAN_INTERVAL = timedelta(seconds=3600)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the WorldTidesInfo sensor."""
    name = config.get(CONF_NAME)

    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)
    key = config.get(CONF_API_KEY)

    if None in (lat, lon):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")

    add_devices([WorldTidesInfoSensor(name, lat, lon, key)], True)


class WorldTidesInfoSensor(Entity):
    """Representation of a WorldTidesInfo sensor."""

    def __init__(self, name, lat, lon, key):
        """Initialize the sensor."""
        self._name = name
        self._lat = lat
        self._lon = lon
        self._key = key
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {}
        if "High" in str(self.data['extremes'][0]['type']):
            attr['high_tide_time_utc'] = self.data['extremes'][0]['date']
            attr['high_tide_height'] = self.data['extremes'][0]['height']
            attr['low_tide_time_utc'] = self.data['extremes'][1]['date']
            attr['low_tide_height'] = self.data['extremes'][1]['height']
        elif "Low" in str(self.data['extremes'][0]['type']):
            attr['high_tide_time_utc'] = self.data['extremes'][1]['date']
            attr['high_tide_height'] = self.data['extremes'][1]['height']
            attr['low_tide_time_utc'] = self.data['extremes'][0]['date']
            attr['low_tide_height'] = self.data['extremes'][0]['height']
        return attr

    @property
    def state(self):
        """Return the state of the device."""
        if self.data:
            if "High" in str(self.data['extremes'][0]['type']):
                tidetime = time.strftime('%I:%M %p', time.localtime(
                    self.data['extremes'][0]['dt']))
                return "High tide at %s" % (tidetime)
            elif "Low" in str(self.data['extremes'][0]['type']):
                tidetime = time.strftime('%I:%M %p', time.localtime(
                    self.data['extremes'][0]['dt']))
                return "Low tide at %s" % (tidetime)
            return STATE_UNKNOWN
        return STATE_UNKNOWN

    def update(self):
        """Get the latest data from WorldTidesInfo API."""
        start = int(time.time())
        resource = 'https://www.worldtides.info/api?extremes&length=86400' \
                   '&key=%s&lat=%s&lon=%s&start=%s' % (self._key, self._lat,
                                                       self._lon, start)

        try:
            self.data = requests.get(resource, timeout=10).json()
            _LOGGER.debug("Data = %s", self.data)
            _LOGGER.info("Tide data queried with start time set to: %s",
                         (start))
        except ValueError as err:
            _LOGGER.error("Check WorldTidesInfo %s", err.args)
            self.data = None
            raise
