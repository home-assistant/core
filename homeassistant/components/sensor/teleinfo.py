"""
Support for Teleinfo sensors.

Teleinfo is a French specific protocol used in electricity smart meters.
It provides real time information on power consumption, rates and current on
a user accessible serial port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.teleinfo/
"""

import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_DEVICE, CONF_NAME, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle


REQUIREMENTS = ["kylin==0.5.0"]

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Provided by EDF Teleinfo."

DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_NAME = 'teleinfo'

DATA_TELEINFO = "data_teleinfo"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

TELEINFO_AVAILABLE_VALUES = ['HCHC', 'HCHP', 'IINST', 'IMAX', 'PAPP', 'ISOUSC']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up for the Teleinfo device."""
    from kylin import exceptions

    teleinfo_data = None
    try:
        import kylin
        teleinfo = kylin.Kylin(port=config.get(CONF_DEVICE), timeout=2)
        teleinfo_data = TeleinfoData(hass, teleinfo)

    except exceptions.KylinSerialError as err:
        return False

    if not teleinfo_data.update():
        _LOGGER.critical("Can't retrieve Teleinfo from device")
        return False

    add_devices([TeleinfoSensor(teleinfo_data, config.get(CONF_NAME))], True)


class TeleinfoSensor(Entity):
    """Implementation of the Teleinfo sensor."""

    def __init__(self, teleinfo_data, name):
        """Initialize the sensor."""
        self._name = name
        self._unit_of_measurement = None
        self._state = STATE_UNKNOWN
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        self._data = teleinfo_data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from Teleinfo device and updates the state."""
        self._data.update()
        if self._data.frame:
            _LOGGER.debug("Frame read: %s", self._data.frame)
            for info in self._data.frame:
                if info['name'] in TELEINFO_AVAILABLE_VALUES:
                    self._attributes[info['name']] = int(info['value'])
                else:
                    self._attributes[info['name']] = info['value']
                if 'ADCO' == info['name']:
                    self._state = self._attributes['ADCO']
            _LOGGER.debug("Sensor: %s %s", self._state, self._attributes)


class TeleinfoData(object):
    """Get the latest data from Teleinfo."""

    def __init__(self, hass, teleinfo):
        """Initialize the data object."""
        self._frame = None
        self._teleinfo = teleinfo

    @property
    def teleinfo(self):
        """Return the Teleinfo object."""
        return self._teleinfo

    @property
    def frame(self):
        """Return the Teleinfo frame data."""
        return self._frame

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Teleinfo device."""
        self._teleinfo.open()
        self._frame = self._teleinfo.readframe()
        self._teleinfo.close()
        if not self._frame:
            _LOGGER.warning("Don't receive energy data from Teleinfo!")
            return None
        return self._frame

    def _stop(self, event):
        """HA is shutting down, close port."""
        if self._teleinfo is not None:
            self._teleinfo.close()
            self._teleinfo = None
        return
