"""
Connects to LCN platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lcn/
"""

import logging

import voluptuous as vol

from homeassistant.components.lcn.core import (
    CONF_CONNECTIONS, CONF_DIM_MODE, CONF_SK_NUM_TRIES, DIM_MODES,
    get_connection)
from homeassistant.const import (
    CONF_ADDRESS, CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pypck==0.5.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lcn'
DATA_LCN = 'lcn'
LIB_LCN = 'pypck'
DEFAULT_NAME = 'pchk'

CONNECTION_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SK_NUM_TRIES, default=3): cv.positive_int,
    vol.Optional(CONF_DIM_MODE, default='steps50'): vol.Any(*DIM_MODES),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CONNECTIONS): vol.Schema([CONNECTION_SCHEMA])
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the LCN component."""
    import pypck
    from pypck.connection import PchkConnectionManager

    hass.data[DATA_LCN] = {}
    hass.data[DATA_LCN][LIB_LCN] = pypck

    conf_connections = config[DOMAIN][CONF_CONNECTIONS]
    connections = []
    connection_names = []
    for conf_connection in conf_connections:
        # use 'pchk' as default connection_id (or add a numeric suffix if
        # pchk' is already in use
        connection_name = conf_connection[CONF_NAME]
        if connection_name == DEFAULT_NAME:
            while connection_name in connection_names:
                suffix = connection_name.strip(DEFAULT_NAME)
                c_id = 1 if not suffix else int(suffix) + 1
                connection_name = '{}{:d}'.format(DEFAULT_NAME, c_id)
        connection_names.append(connection_name)

        settings = {'SK_NUM_TRIES': conf_connection[CONF_SK_NUM_TRIES],
                    'DIM_MODE': pypck.lcn_defs.OutputPortDimMode[
                        conf_connection[CONF_DIM_MODE].upper()]}

        connection = PchkConnectionManager(hass.loop,
                                           conf_connection[CONF_HOST],
                                           conf_connection[CONF_PORT],
                                           conf_connection[CONF_USERNAME],
                                           conf_connection[CONF_PASSWORD],
                                           settings=settings,
                                           connection_id=connection_name)

        # establish connection to PCHK server
        try:
            await hass.async_create_task(connection.async_connect())
            connections.append(connection)
            _LOGGER.info('LCN connected to "{:s}"'.format(connection_name))
        except TimeoutError:
            _LOGGER.error('Connection to PCHK server "{:s}" failed.'.format(
                connection_name))
            return False

    hass.data[DATA_LCN][CONF_CONNECTIONS] = connections
    return True


class LcnDevice(Entity):
    """Parent class for all devices associated with the LCN component."""

    def __init__(self, hass, config):
        """Initialize the LCN device."""
        self.hass = hass
        self.pypck = hass.data[DATA_LCN][LIB_LCN]
        self._name = config[CONF_NAME]

        address, connection_id = config[CONF_ADDRESS]
        addr = self.pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)

        self.address_connection = connection.get_address_conn(addr)
        self.address_connection.register_for_inputs(
            self.input_received)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj):
        """Set state/value when LCN input object (command) is received."""
        raise NotImplementedError('Pure virtual function.')
