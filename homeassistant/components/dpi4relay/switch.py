"""Support for switch sensor using DockerPi 4 Channel Relay expansion board."""
import logging

import voluptuous as vol
from smbus2 import SMBus

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_I2C_BUS = "i2c_bus"
CONF_I2C_ADDRESS = "i2c_address"
CONF_PINS = "pins"

DEFAULT_I2C_BUS = 1
DEFAULT_I2C_ADDRESS = 0x10

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): cv.positive_int,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up devices."""
    i2c_address = config.get(CONF_I2C_ADDRESS)
    bus_num = config.get(CONF_I2C_BUS)

    bus = SMBus(bus_num)

    switches = []
    pins = config.get(CONF_PINS)
    for pin_num, pin_name in pins.items():
        def setState(state, pin_num=pin_num):
            if state:
                data = 0xFF
            else:
                data = 0x00
            bus.write_byte_data(i2c_address, pin_num, data)
        switches.append(Dpi4RelaySwitch(pin_name, setState))
    add_entities(switches)


class Dpi4RelaySwitch(ToggleEntity):
    """Representation of DockerPi 4 Channel Relay output pin."""

    def __init__(self, name, setState):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._setState = setState
        self._state = False

        self._setState(False)

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

    @property
    def assumed_state(self):
        """Return true if optimistic updates are used."""
        return True

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._setState(True)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._setState(False)
        self._state = False
        self.schedule_update_ha_state()
