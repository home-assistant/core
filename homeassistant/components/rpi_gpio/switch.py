"""Allows to configure a switch using RPi GPIO."""
import voluptuous as vol

from homeassistant.components import rpi_gpio
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.reload import setup_reload_service

from . import DOMAIN, PLATFORMS

CONF_PULL_MODE = "pull_mode"
CONF_PORTS = "ports"
CONF_INVERT_LOGIC = "invert_logic"

DEFAULT_INVERT_LOGIC = False

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PORTS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""
    setup_reload_service(hass, DOMAIN, PLATFORMS)

    invert_logic = config.get(CONF_INVERT_LOGIC)

    switches = []
    ports = config.get(CONF_PORTS)
    for port, name in ports.items():
        switches.append(RPiGPIOSwitch(name, port, invert_logic))
    add_entities(switches, True)


class RPiGPIOSwitch(ToggleEntity):
    """Representation of a  Raspberry Pi GPIO."""

    def __init__(self, name, port, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._on_state = 0 if invert_logic else 1
        rpi_gpio.setup_output(self._port)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return True

    @property
    def is_on(self):
        """Return true if device is on."""
        return rpi_gpio.read_input(self._port) == self._on_state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rpi_gpio.write_output(self._port, self._on_state)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        rpi_gpio.write_output(self._port, 1 - self._on_state)
        self.schedule_update_ha_state()
