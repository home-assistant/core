"""Pencom relay control.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/pencom
"""
import logging

import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
import homeassistant.helpers.config_validation as cv

# Home Assistant depends on 3rd party packages for API specific code.
REQUIREMENTS = ['pencompy==0.0.3']

_LOGGER = logging.getLogger(__name__)

# Number of boards connected to the serial port
CONF_BOARDS = 'boards'
CONF_BOARD = 'board'
CONF_ADDR = 'addr'
CONF_RELAYS = 'relays'
CONF_RELAY = 'relay'

RELAY_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDR): cv.positive_int,
    vol.Optional(CONF_BOARD, default=0): cv.positive_int,
})

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Optional(CONF_BOARDS, default=1): cv.positive_int,
    vol.Required(CONF_RELAYS): vol.All(cv.ensure_list, [RELAY_SCHEMA]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Pencom relay platform (pencompy)."""
    from pencompy.pencompy import Pencompy

    # Assign configuration variables.
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    boards = config.get(CONF_BOARDS)

    # Setup connection with devices/cloud.
    try:
        hub = Pencompy(host, port, boards=boards)
    except OSError as error:
        _LOGGER.error("Could not connect to pencompy: %s", error)
        return False

    # Add devices.
    devs = []
    for relay in config.get(CONF_RELAYS):
        name = relay.get(CONF_NAME)
        board = relay.get(CONF_BOARD)
        addr = relay.get(CONF_ADDR)
        devs.append(PencomRelay(hub, board, addr, name))
    add_devices(devs, True)
    return True


class PencomRelay(SwitchDevice):
    """Representation of a pencom relay."""

    def __init__(self, hub, board, addr, name):
        """Create a relay."""
        self._hub = hub
        self._board = board
        self._addr = addr
        self._state = None
        self._name = name

    @property
    def name(self):
        """Relay name."""
        return self._name

    @property
    def is_on(self):
        """Return a relay's state."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn a relay on."""
        self._hub.set(self._board, self._addr, True)

    def turn_off(self, **kwargs):
        """Turn a relay off."""
        self._hub.set(self._board, self._addr, False)

    def update(self):
        """Refresh a relay's state."""
        self._state = self._hub.get(self._board, self._addr)

    @property
    def device_state_attributes(self):
        """Return supported attributes."""
        return {"Board": self._board,
                "Addr": self._addr}
