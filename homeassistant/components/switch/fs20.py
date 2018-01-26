"""
FS20 switch from ELV, can be controlled remotely via a FHZ PC device.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/fhz/
"""
import asyncio
import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components import (fhz)
from homeassistant.const import (CONF_NAME, CONF_CODE)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'FS20 switch'
DEFAULT_NUMBER_OF_REPEATS = 1
CONF_NUMBER_OF_REPEATS = 'number_of_repeats'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(
        CONF_NUMBER_OF_REPEATS,
        default=DEFAULT_NUMBER_OF_REPEATS): cv.positive_int,
    vol.Required(CONF_CODE): fhz.base4plus1_length_4,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a FS20 switch."""
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)
    number_of_repeats = config.get(CONF_NUMBER_OF_REPEATS)

    byte_code = code_to_byte(code)
    add_devices([FS20Switch(hass, name, byte_code, number_of_repeats)], True)


class FS20Switch(SwitchDevice):
    """Representation of a FS20 switch."""

    def __init__(self, hass, name, code, number_of_repeats):
        """Initialize the FS20 switch."""
        self._code = code
        self._hass = hass
        self._name = name
        self._number_of_repeats = number_of_repeats
        self._state = False

    @property
    def should_poll(self):
        """We cannot check the state of the switch."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn the device on."""
        fhz.DEVICE.send_fs20_command(
            self._code, fhz.COMMAND_ON, self._number_of_repeats)
        self._state = True
        self.hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn the device off."""
        fhz.DEVICE.send_fs20_command(
            self._code, fhz.COMMAND_OFF, self._number_of_repeats)
        self._state = False
        self.hass.async_add_job(self.async_update_ha_state())

    def update(self):
        """Cannot check if device is on."""


def code_to_byte(value):
    """Convert an address string in the "base 4 + 1" format."""
    return fhz.code_to_int(value) & 0xFF
