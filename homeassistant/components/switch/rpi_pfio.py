"""
Allows to configure a switch using the PiFace Digital I/O module on a RPi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rpi_pfio/
"""
import logging

import voluptuous as vol

import homeassistant.components.rpi_pfio as rpi_pfio
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['rpi_pfio']

ATTR_INVERT_LOGIC = 'invert_logic'
ATTR_NAME = 'name'

CONF_PORTS = 'ports'

DEFAULT_INVERT_LOGIC = False

PORT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORTS, default={}): vol.Schema({
        cv.positive_int: PORT_SCHEMA,
    })
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the PiFace Digital Output devices."""
    switches = []
    ports = config.get(CONF_PORTS)
    for port, port_entity in ports.items():
        name = port_entity.get(ATTR_NAME)
        invert_logic = port_entity[ATTR_INVERT_LOGIC]

        switches.append(RPiPFIOSwitch(port, name, invert_logic))
    add_devices(switches)


class RPiPFIOSwitch(ToggleEntity):
    """Representation of a PiFace Digital Output."""

    def __init__(self, port, name, invert_logic):
        """Initialize the pin."""
        self._port = port
        self._name = name or DEVICE_DEFAULT_NAME
        self._invert_logic = invert_logic
        self._state = False
        rpi_pfio.write_output(self._port, 1 if self._invert_logic else 0)

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

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rpi_pfio.write_output(self._port, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        rpi_pfio.write_output(self._port, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
