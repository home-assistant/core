"""Support for switches using the PiFace Digital I/O module on a RPi."""
import logging

import voluptuous as vol

from homeassistant.components import rpi_pfio2
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import ATTR_NAME, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['rpi_pfio2']

ATTR_INVERT_LOGIC = 'invert_logic'
ATTR_INITIAL_STATE = "initial_state"

CONF_PORTS = 'ports'

CONF_BOARDS = 'boards'

DEFAULT_INVERT_LOGIC = False
DEFAULT_INITIAL_STATE = False

PORT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    vol.Optional(ATTR_INITIAL_STATE,
                 default=DEFAULT_INITIAL_STATE): cv.boolean,
})

BOARD_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORTS, default={}): vol.Schema({
        cv.positive_int: PORT_SCHEMA,
    })
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BOARDS, default={}): vol.Schema({
        cv.positive_int: BOARD_SCHEMA,
    })
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PiFace Digital Output devices."""
    switches = []
    boards = config.get(CONF_BOARDS)
    for board, board_entity in boards.items():
        ports = board_entity.get(CONF_PORTS)
        for port, port_entity in ports.items():
            name = port_entity.get(ATTR_NAME)
            invert_logic = port_entity[ATTR_INVERT_LOGIC]
            initial_state = port_entity[ATTR_INITIAL_STATE]
            switches.append(RPiPFIOSwitch(port, name, invert_logic,
                                          initial_state, board))
    add_entities(switches)


class RPiPFIOSwitch(ToggleEntity):
    """Representation of a PiFace Digital Output."""

    def __init__(self, port, name, invert_logic, initial_state,
                 hardware_addr=0):
        """Initialize the pin."""
        self._port = port
        self._name = name or DEVICE_DEFAULT_NAME
        self._invert_logic = invert_logic
        self._initial_state = initial_state
        self._hardware_addr = hardware_addr
        self._state = initial_state
        if self._invert_logic == self._initial_state:
            state_to_set = 0
        else:
            state_to_set = 1
        rpi_pfio2.write_output(self._port, state_to_set, self._hardware_addr)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def hardware_addr(self):
        """Return the hardware address."""
        return self._hardware_addr

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rpi_pfio2.write_output(self._port, 0 if self._invert_logic else 1,
                               self._hardware_addr)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        rpi_pfio2.write_output(self._port, 1 if self._invert_logic else 0,
                               self._hardware_addr)
        self._state = False
        self.schedule_update_ha_state()
