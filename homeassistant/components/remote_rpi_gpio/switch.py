"""Allows to configure a switch using RPi GPIO."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.components import remote_rpi_gpio
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['remote_rpi_gpio']

CONF_ADDRESS = 'address'
CONF_PULL_MODE = 'pull_mode'
CONF_PORTS = 'ports'
CONF_INVERT_LOGIC = 'invert_logic'

DEFAULT_INVERT_LOGIC = False

_SWITCHES_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Required(CONF_PORTS): _SWITCHES_SCHEMA,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Remote Raspberry PI GPIO devices."""
    address = config.get(CONF_ADDRESS)
    invert_logic = config.get(CONF_INVERT_LOGIC)

    switches = []
    ports = config.get(CONF_PORTS)
    for port, name in ports.items():
        switches.append(RemoteRPiGPIOSwitch(name, address, port, invert_logic))
    add_entities(switches)


class RemoteRPiGPIOSwitch(ToggleEntity):
    """Representation of a Remtoe Raspberry Pi GPIO."""

    def __init__(self, name, address, port, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._address = address
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        self._switch = None

        try:
            self._switch = remote_rpi_gpio.setup_output(self._address, self._port, self._invert_logic)
        except (ValueError, IndexError, KeyError):
            return None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        print("turning on switch: ", self._switch)
        remote_rpi_gpio.write_output(self._switch, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        remote_rpi_gpio.write_output(self._switch, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
