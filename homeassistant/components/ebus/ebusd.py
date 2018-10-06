"""
Support for Ebusd daemon for communication with eBUS heating systems.

For more details about ebusd deamon, please refer to the documentation at
https://github.com/john30/ebusd
"""

from datetime import timedelta
import logging
import socket

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_MONITORED_CONDITIONS,
    STATE_ON, STATE_OFF)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    DOMAIN, SENSOR_TYPES, READ_COMMAND, WRITE_COMMAND)

REQUIREMENTS = ['ebusdpy==0.0.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'ebusd'
DEFAULT_PORT = 8888
CONF_CIRCUIT = 'circuit'
CACHE_TTL = 900
SERVICE_EBUSD_WRITE = 'ebusd_write'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CIRCUIT): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ebusd..."""
    name = config.get(CONF_NAME)
    circuit = config.get(CONF_CIRCUIT)
    server_address = (config.get(CONF_HOST), config.get(CONF_PORT))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data = EbusdData(server_address, circuit)

        sock.settimeout(5)
        sock.connect(server_address)
        sock.close()

        dev = []
        for variable in config[CONF_MONITORED_CONDITIONS]:
            dev.append(Ebusd(data, variable, name))

        add_devices(dev)
        hass.services.register(DOMAIN, SERVICE_EBUSD_WRITE, data.write)
    except socket.timeout:
        raise PlatformNotReady
    except socket.error:
        raise PlatformNotReady


def timer_format(string):
    """Datetime formatter."""
    _r = []
    _s = string.split(';')
    for i in range(0, len(_s) // 2):
        if(_s[i * 2] != '-:-' and _s[i * 2] != _s[(i * 2) + 1]):
            _r.append(_s[i * 2] + '/' + _s[(i * 2) + 1])
    return ' - '.join(_r)


class EbusdData:
    """Get the latest data from Ebusd."""

    def __init__(self, address, circuit):
        """Initialize the data object."""
        self._circuit = circuit
        self._address = address
        self.value = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, name):
        """Call the Ebusd API to update the data."""
        import ebusdpy
        command = READ_COMMAND.format(self._circuit, name, CACHE_TTL)

        try:
            _LOGGER.debug("Opening socket to ebusd %s: %s", name, command)
            command_result = ebusdpy.send_command(self._address, command)
            if 'not found' in command_result:
                _LOGGER.warning("Element not found: %s", name)
                raise RuntimeError("Element not found")
            else:
                self.value[name] = command_result
        except socket.timeout:
            _LOGGER.error("socket timeout error")
            raise RuntimeError("socket timeout")
        except socket.error:
            _LOGGER.error("socket error: %s", socket.error)
            raise RuntimeError("Command failed")

    def write(self, call):
        """Call write methon on ebusd."""
        import ebusdpy
        name = call.data.get('name')
        value = call.data.get('value')
        command = WRITE_COMMAND.format(self._circuit, name, value)

        try:
            _LOGGER.debug("Opening socket to ebusd %s: %s", name, command)
            command_result = ebusdpy.send_command(self._address, command)
            if 'done' not in command_result:
                _LOGGER.warning('Write command failed: %s', name)
        except socket.timeout:
            _LOGGER.error("socket timeout error")
        except socket.error:
            _LOGGER.error()


class Ebusd(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, sensor_type, name):
        """Initialize the sensor."""
        self._state = None
        self._client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self._type = SENSOR_TYPES[sensor_type][3]
        self.data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self.data.update(self._name)
            if self._name not in self.data.value:
                return

            if self._type == 0:
                self._state = format(
                    float(self.data.value[self._name]), '.1f')
            elif self._type == 1:
                self._state = timer_format(self.data.value[self._name])
            elif self._type == 2:
                if self.data.value[self._name] == 1:
                    self._state = STATE_ON
                else:
                    self._state = STATE_OFF
            elif self._type == 3:
                self._state = self.data.value[self._name]
        except RuntimeError:
            _LOGGER.debug("EbusdData.update exception")
