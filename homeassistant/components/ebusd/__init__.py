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
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import Throttle

from .const import (
    DOMAIN, SENSOR_TYPES, READ_COMMAND, WRITE_COMMAND)

REQUIREMENTS = ['ebusdpy==0.0.4']

_LOGGER = logging.getLogger(__name__)

DATA_EBUSD = 'EBUSD'
DEFAULT_NAME = 'ebusd'
DEFAULT_PORT = 8888
CONF_CIRCUIT = 'circuit'
CACHE_TTL = 900
SERVICE_EBUSD_WRITE = 'ebusd_write'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

CONFIG_SCHEMA = vol.Schema({
  DOMAIN: vol.Schema({
    vol.Required(CONF_CIRCUIT): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES['700'])])
  })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the ebusd component."""
    if DOMAIN not in config:
        return True

    name = config[DOMAIN].get(CONF_NAME)
    circuit = config[DOMAIN].get(CONF_CIRCUIT)
    monitored_conditions = config[DOMAIN].get(CONF_MONITORED_CONDITIONS)
    server_address = (config[DOMAIN].get(CONF_HOST), config[DOMAIN].get(CONF_PORT))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hass.data[DATA_EBUSD] = EbusdData(server_address, circuit)

        sock.settimeout(5)
        sock.connect(server_address)
        sock.close()

        sensorConfig = {'monitored_conditions': monitored_conditions, 
           'client_name' : name, 
           'sensor_types': SENSOR_TYPES[circuit]
        }
        load_platform(hass, 'sensor', DOMAIN, sensorConfig, config)

        hass.services.register(DOMAIN, SERVICE_EBUSD_WRITE, hass.data[DATA_EBUSD].write)

        _LOGGER.debug("Ebusd component setup completed.")
        return True        
    except socket.timeout:
        raise PlatformNotReady
    except socket.error:
        raise PlatformNotReady


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
