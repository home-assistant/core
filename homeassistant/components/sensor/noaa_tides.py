"""
Support for the NOAA Tides and Currents API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.noaa_tides/
"""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_TIME_ZONE, CONF_UNIT_SYSTEM)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['py_noaa==0.3.0']

_LOGGER = logging.getLogger(__name__)

CONF_STATION_ID = 'station_id'

DEFAULT_ATTRIBUTION = "Data provided by NOAA"
DEFAULT_NAME = 'NOAA Tides'
DEFAULT_TIMEZONE = 'lst_ldt'

SCAN_INTERVAL = timedelta(minutes=60)

TIMEZONES = ['gmt', 'lst', 'lst_ldt']
UNIT_SYSTEMS = ['english', 'metric']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIME_ZONE, default=DEFAULT_TIMEZONE): vol.In(TIMEZONES),
    vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNIT_SYSTEMS),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NOAA Tides and Currents sensor."""
    station_id = config[CONF_STATION_ID]
    name = config.get(CONF_NAME)
    timezone = config.get(CONF_TIME_ZONE)

    if CONF_UNIT_SYSTEM in config:
        unit_system = config[CONF_UNIT_SYSTEM]
    elif hass.config.units.is_metric:
        unit_system = UNIT_SYSTEMS[1]
    else:
        unit_system = UNIT_SYSTEMS[0]

    noaa_sensor = NOAATidesAndCurrentsSensor(
        name, station_id, timezone, unit_system)

    noaa_sensor.update()
    if noaa_sensor.data is None:
        _LOGGER.error("Unable to setup NOAA Tides Sensor")
        return
    add_entities([noaa_sensor], True)


class NOAATidesAndCurrentsSensor(Entity):
    """Representation of a NOAA Tides and Currents sensor."""

    def __init__(self, name, station_id, timezone, unit_system):
        """Initialize the sensor."""
        self._name = name
        self._station_id = station_id
        self._timezone = timezone
        self._unit_system = unit_system
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        if self.data is None:
            return attr
        if self.data['hi_lo'][1] == 'H':
            attr['high_tide_time'] = \
                self.data.index[1].strftime('%Y-%m-%dT%H:%M')
            attr['high_tide_height'] = self.data['predicted_wl'][1]
            attr['low_tide_time'] = \
                self.data.index[2].strftime('%Y-%m-%dT%H:%M')
            attr['low_tide_height'] = self.data['predicted_wl'][2]
        elif self.data['hi_lo'][1] == 'L':
            attr['low_tide_time'] = \
                self.data.index[1].strftime('%Y-%m-%dT%H:%M')
            attr['low_tide_height'] = self.data['predicted_wl'][1]
            attr['high_tide_time'] = \
                self.data.index[2].strftime('%Y-%m-%dT%H:%M')
            attr['high_tide_height'] = self.data['predicted_wl'][2]
        return attr

    @property
    def state(self):
        """Return the state of the device."""
        if self.data is None:
            return None
        api_time = self.data.index[0]
        if self.data['hi_lo'][0] == 'H':
            tidetime = api_time.strftime('%-I:%M %p')
            return "High tide at {}".format(tidetime)
        if self.data['hi_lo'][0] == 'L':
            tidetime = api_time.strftime('%-I:%M %p')
            return "Low tide at {}".format(tidetime)
        return None

    def update(self):
        """Get the latest data from NOAA Tides and Currents API."""
        from py_noaa import coops  # pylint: disable=import-error
        begin = datetime.now()
        delta = timedelta(days=2)
        end = begin + delta
        try:
            df_predictions = coops.get_data(
                begin_date=begin.strftime("%Y%m%d %H:%M"),
                end_date=end.strftime("%Y%m%d %H:%M"),
                stationid=self._station_id,
                product="predictions",
                datum="MLLW",
                interval="hilo",
                units=self._unit_system,
                time_zone=self._timezone)
            self.data = df_predictions.head()
            _LOGGER.debug("Data = %s", self.data)
            _LOGGER.debug("Recent Tide data queried with start time set to %s",
                          begin.strftime("%m-%d-%Y %H:%M"))
        except ValueError as err:
            _LOGGER.error("Check NOAA Tides and Currents: %s", err.args)
            self.data = None
