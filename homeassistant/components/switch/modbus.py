"""
Support for Modbus switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.modbus/
"""
import logging
import voluptuous as vol

import homeassistant.components.modbus as modbus
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers import config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']

CONF_COIL = "coil"
CONF_COILS = "coils"
CONF_SLAVE = "slave"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COILS): [{
        vol.Required(CONF_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int,
    }]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Read configuration and create Modbus devices."""
    switches = []
    for coil in config.get("coils"):
        switches.append(ModbusCoilSwitch(
            coil.get(CONF_NAME),
            coil.get(CONF_SLAVE),
            coil.get(CONF_COIL)))
    add_devices(switches)


class ModbusCoilSwitch(ToggleEntity):
    """Representation of a Modbus switch."""

    def __init__(self, name, slave, coil):
        """Initialize the switch."""
        self._name = name
        self._slave = int(slave) if slave else None
        self._coil = int(coil)
        self._is_on = None

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Set switch on."""
        modbus.HUB.write_coil(self._slave, self._coil, True)

    def turn_off(self, **kwargs):
        """Set switch off."""
        modbus.HUB.write_coil(self._slave, self._coil, False)

    def update(self):
        """Update the state of the switch."""
        result = modbus.HUB.read_coils(self._slave, self._coil, 1)
        if not result:
            _LOGGER.error(
                'No response from modbus slave %s coil %s',
                self._slave,
                self._coil)
            return
        self._is_on = bool(result.bits[0])
