"""
This component provides HA sensor support for the NOAA Tides and Currents API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.noaa_tides/
"""
import logging
import time
from datetime import datetime, timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION, CONF_NAME, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['py_noaa==0.2.2']

_LOGGER = logging.getLogger(__name__)

API_URL = 'https://tidesandcurrents.noaa.gov/api/datagetter'
CONF_STA_ID = 'station_id'
CONF_TZ = 'timezone'
CONF_UNITS = 'units'
DEFAULT_ATTRIBUTION = "Data provided by NOAA"
DEFAULT_NAME = 'NOAA Tides'
DEFAULT_TZ = 'lst_ldt'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=60)

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
        if "H" == self.data['hi_lo'][1]:
            attr['high_tide_time'] = self.data.index[1].strftime('%I:%M %p')
            attr['high_tide_height'] = self.data['predicted_wl'][1]
            attr['low_tide_time'] = self.data.index[2].strftime('%I:%M %p')
            attr['low_tide_height'] = self.data['predicted_wl'][2]
        elif "L" == self.data['hi_lo'][1]:
            attr['low_tide_time'] = self.data.index[1].strftime('%I:%M %p')
            attr['low_tide_height'] = self.data['predicted_wl'][1]
            attr['high_tide_time'] = self.data.index[2].strftime('%I:%M %p')
            attr['high_tide_height'] = self.data['predicted_wl'][2]
        return attr

    @property
    def state(self):
        """Return the state of the device."""
        if self.data is not None:
            api_time = self.data.index[0]
            if "H" == self.data['hi_lo'][0]:
                tidetime = api_time.strftime('%I:%M %p')
                return "High tide at %s" % (tidetime)
            if "L" == self.data['hi_lo'][0]:
                tidetime = api_time.strftime('%I:%M %p')
                return "Low tide at %s" % (tidetime)
            return STATE_UNKNOWN
        return STATE_UNKNOWN

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from NOAA Tides and Currents API."""
        from py_noaa import coops
        begin = datetime.now()
        delta = timedelta(days=2)
        end = begin + delta
        try:
            df = coops.get_data(
                begin_date=begin.strftime("%Y%m%d %H:%M"),
                end_date=end.strftime("%Y%m%d %H:%M"),
                stationid=self._sta,
                product="predictions",
                datum="MLLW",
                interval="hilo",
                units=self._units,
                time_zone=self._tz)
            self.data = df.head()
            _LOGGER.debug("Data = %s", self.data)
            _LOGGER.info("Recent Tide data queried with start time set to %s", begin.strftime("%m-%d-%Y %H:%M"))
        except ValueError as err:
            _LOGGER.error("Check NOAA Tides and Currents %s", err.args)
            self.data = None
            raise
