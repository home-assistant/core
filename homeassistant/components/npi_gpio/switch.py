"""Allows to configure a switch using NPi GPIO."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.components import npi_gpio
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)



CONF_PORTS = 'ports'
CONF_INVERT_LOGIC = 'invert_logic'
CONF_INITIAL = 'initial'

DEFAULT_INVERT_LOGIC = False

_SWITCHES_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORTS): _SWITCHES_SCHEMA,
    vol.Optional(CONF_INITIAL, default=False): cv.boolean,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""
    invert_logic = config.get(CONF_INVERT_LOGIC)

    switches = []
    ports = config.get(CONF_PORTS)
    for port, name in ports.items():
        switches.append(NPiGPIOSwitch(name, port, invert_logic))
    add_entities(switches)


class NPiGPIOSwitch(ToggleEntity):
    """Representation of a NanoPi NEO GPIO."""

    def __init__(self, name, port, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._invert_logic = invert_logic
        self._state = params.get(CONF_INITIAL)
        npi_gpio.setup_output(self._port)
        npi_gpio.write_output(self._port, 1 if self._invert_logic else 0)

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
        npi_gpio.write_output(self._port, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        npi_gpio.write_output(self._port, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
