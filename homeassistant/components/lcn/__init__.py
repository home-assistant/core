"""
Connects to LCN platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lcn/
"""

import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .core import (
    CONF_ADDRESS, CONF_CONNECTIONS, CONF_DIM_MODE, CONF_SK_NUM_TRIES,
    DIM_MODES, get_connection)

REQUIREMENTS = ['pypck==0.5.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lcn'
DATA_LCN = 'lcn'
LIB_LCN = 'pypck'
DEFAULT_NAME = 'pchk'

CONNECTION_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.positive_int,
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

    from .services import (OutputAbs, OutputRel, OutputToggle, Relays, VarAbs,
                           VarReset, VarRel, LockRegulator, Led, SendKeys,
                           LockKeys, DynText, Pck)

    hass.data[DATA_LCN] = {}
    hass.data[DATA_LCN][CONF_CONNECTIONS] = {}
    hass.data[DATA_LCN][LIB_LCN] = pypck

    domain_config = config[DOMAIN]
    conf_connections = domain_config[CONF_CONNECTIONS]
    connection_ids = []
    connections = []
    for conf_connection in conf_connections:
        ip_address = conf_connection[CONF_HOST]
        port = conf_connection[CONF_PORT]
        username = conf_connection[CONF_USERNAME]
        password = conf_connection[CONF_PASSWORD]

        settings = {}
        settings['SK_NUM_TRIES'] = conf_connection[CONF_SK_NUM_TRIES]
        settings['DIM_MODE'] = pypck.lcn_defs.OutputPortDimMode[
            conf_connection[CONF_DIM_MODE].upper()]

        # use 'pchk' as default connection_id (or add a numeric suffix if
        # pchk' is already in use
        connection_id = conf_connection[CONF_NAME]
        if connection_id == DEFAULT_NAME:
            while connection_id in connection_ids:
                suffix = connection_id.strip(DEFAULT_NAME)
                c_id = 1 if not suffix else int(suffix) + 1
                connection_id = '{}{:d}'.format(DEFAULT_NAME, c_id)

        connection_ids.append(connection_id)

        connection = PchkConnectionManager(hass.loop, ip_address, port,
                                           username, password,
                                           settings=settings,
                                           connection_id=connection_id)
        connections.append(connection)

        # establish connection to PCHK server
        try:
            await hass.async_create_task(connection.connect())
            hass.data[DATA_LCN][CONF_CONNECTIONS] = connections
            _LOGGER.info('LCN connected to "{:s}"'.format(connection_id))
            # await hass.loop.create_task(connection.connect())
        except TimeoutError:
            _LOGGER.error('Connection to PCHK server "{:s}" failed.'.format(
                connection_id))
            return False

    # register service calls
    hass.services.async_register(DOMAIN, 'output_abs',
                                 OutputAbs(hass), OutputAbs.schema)

    hass.services.async_register(DOMAIN, 'output_rel',
                                 OutputRel(hass), OutputRel.schema)

    hass.services.async_register(DOMAIN, 'output_toggle',
                                 OutputToggle(hass), OutputToggle.schema)

    hass.services.async_register(DOMAIN, 'relays',
                                 Relays(hass), Relays.schema)

    hass.services.async_register(DOMAIN, 'var_abs',
                                 VarAbs(hass), VarAbs.schema)

    hass.services.async_register(DOMAIN, 'var_reset',
                                 VarReset(hass), VarReset.schema)

    hass.services.async_register(DOMAIN, 'var_rel',
                                 VarRel(hass), VarRel.schema)

    hass.services.async_register(DOMAIN, 'lock_regulator',
                                 LockRegulator(hass), LockRegulator.schema)

    hass.services.async_register(DOMAIN, 'led',
                                 Led(hass), Led.schema)

    hass.services.async_register(DOMAIN, 'send_keys',
                                 SendKeys(hass), SendKeys.schema)

    hass.services.async_register(DOMAIN, 'lock_keys',
                                 LockKeys(hass), LockKeys.schema)

    hass.services.async_register(DOMAIN, 'dyn_text',
                                 DynText(hass), DynText.schema)

    hass.services.async_register(DOMAIN, 'pck',
                                 Pck(hass), Pck.schema)

    return True


class LcnDevice(Entity):
    """Parent class for all devices associated with the LCN component."""

    def __init__(self, hass, config):
        """Initialize the LCN device."""
        self.hass = hass
        self.pypck = hass.data[DATA_LCN][LIB_LCN]

        addr, connection_id = config[CONF_ADDRESS]
        addr = self.pypck.lcn_addr.LcnAddr(*addr)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        if connection_id is None:
            connection = connections[0]
        else:
            connection = get_connection(connections, connection_id)

        self._name = config[CONF_FRIENDLY_NAME]

        self.module_connection = connection.get_address_conn(addr)
        self.module_connection.register_for_module_inputs(
            self.module_input_received)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def module_input_received(self, input_obj):
        """Set state/value when LCN input object (command) is received."""
        raise NotImplementedError('Pure virtual function.')
