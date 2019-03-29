"""Allows to configure a switch using Orange Pi GPIO."""
import logging

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.components import orangepi_gpio
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity

from . import CONF_PINMODE
from .const import CONF_INVERT_LOGIC, CONF_PORTS, PORT_SCHEMA

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['orangepi_gpio']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(PORT_SCHEMA)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Orange Pi GPIO devices."""
    pinmode = config.get(CONF_PINMODE)
    orangepi_gpio.setup_mode(pinmode)

    invert_logic = config[CONF_INVERT_LOGIC]

    switches = []
    ports = config.get(CONF_PORTS)
    for port, name in ports.items():
        switches.append(OPiGPIOSwitch(name, port, invert_logic))
    add_entities(switches)


class OPiGPIOSwitch(ToggleEntity):
    """Representation of a Orange Pi GPIO."""

    def __init__(self, name, port, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        orangepi_gpio.setup_output(self._port)
        orangepi_gpio.write_output(self._port, 1 if self._invert_logic else 0)

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
        orangepi_gpio.write_output(self._port, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        orangepi_gpio.write_output(self._port, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
