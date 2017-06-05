"""
Support for getting the disk temperature of a host.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hddtemp/
"""
import logging
from datetime import timedelta
from telnetlib import Telnet

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_MODEL = 'model'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 7634
DEFAULT_NAME = 'HD Temperature'
DEFAULT_TIMEOUT = 5

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HDDTemp sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    hddtemp = HddTempData(host, port)
    hddtemp.update()

    if hddtemp.data is None:
        _LOGGER.error("Unable to fetch the data from %s:%s", host, port)
        return False

    add_devices([HddTempSensor(name, hddtemp)], True)


class HddTempSensor(Entity):
    """Representation of a HDDTemp sensor."""

    def __init__(self, name, hddtemp):
        """Initialize a HDDTemp sensor."""
        self.hddtemp = hddtemp
        self._name = name
        self._state = False
        self._details = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._details[4] == 'C':
            return TEMP_CELSIUS
        else:
            return TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_DEVICE: self._details[1],
            ATTR_MODEL: self._details[2],
        }

    def update(self):
        """Get the latest data from HDDTemp daemon and updates the state."""
        self.hddtemp.update()

        if self.hddtemp.data is not None:
            self._details = self.hddtemp.data.split('|')
            self._state = self._details[3]
        else:
            self._state = STATE_UNKNOWN


class HddTempData(object):
    """Get the latest data from HDDTemp and update the states."""

    def __init__(self, host, port):
        """Initialize the data object."""
        self.host = host
        self.port = port
        self.data = None

    def update(self):
        """Get the latest data from HDDTemp running as daemon."""
        try:
            connection = Telnet(
                host=self.host, port=self.port, timeout=DEFAULT_TIMEOUT)
            self.data = connection.read_all().decode('ascii')
        except ConnectionRefusedError:
            _LOGGER.error(
                "HDDTemp is not available at %s:%s", self.host, self.port)
            self.data = None
