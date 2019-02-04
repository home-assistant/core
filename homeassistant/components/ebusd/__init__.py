"""
Support for Ebusd daemon for communication with eBUS heating systems.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ebus/
"""

from datetime import timedelta
import logging
import socket

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_MONITORED_CONDITIONS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import Throttle

from .const import (DOMAIN, SENSOR_TYPES)

REQUIREMENTS = ['ebusdpy==0.0.16']

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
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES['700'])])
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the ebusd component."""
    conf = config[DOMAIN]
    name = conf.get(CONF_NAME)
    circuit = conf.get(CONF_CIRCUIT)
    monitored_conditions = conf.get(CONF_MONITORED_CONDITIONS)
    server_address = (
        conf.get(CONF_HOST), conf.get(CONF_PORT))

    try:
        import ebusdpy
        ebusdpy.init(server_address)
        hass.data[DATA_EBUSD] = EbusdData(server_address, circuit)

        sensor_config = {
            'monitored_conditions': monitored_conditions,
            'client_name': name,
            'sensor_types': SENSOR_TYPES[circuit]
        }
        load_platform(hass, 'sensor', DOMAIN, sensor_config, config)

        hass.services.register(
            DOMAIN, SERVICE_EBUSD_WRITE, hass.data[DATA_EBUSD].write)

        _LOGGER.debug("Ebusd component setup completed.")
        return True
    except socket.timeout:
        return False
    except socket.error:
        return False


class EbusdData:
    """Get the latest data from Ebusd."""

    def __init__(self, address, circuit):
        """Initialize the data object."""
        self._circuit = circuit
        self._address = address
        self.value = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, name, stype):
        """Call the Ebusd API to update the data."""
        import ebusdpy

        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.read(
                self._address, self._circuit, name, stype, CACHE_TTL)
            if 'ERR:' in command_result:
                _LOGGER.error(command_result)
                raise RuntimeError("Error in reading ebus")
            else:
                self.value[name] = command_result
        except RuntimeError as err:
            _LOGGER.error(err)
            raise RuntimeError(err)

    def write(self, call):
        """Call write methon on ebusd."""
        import ebusdpy
        name = call.data.get('name')
        value = call.data.get('value')

        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.write(
                self._address, self._circuit, name, value)
            if 'done' not in command_result:
                _LOGGER.warning('Write command failed: %s', name)
        except socket.timeout:
            _LOGGER.error("socket timeout error")
        except socket.error:
            _LOGGER.error()
