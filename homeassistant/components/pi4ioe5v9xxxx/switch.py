"""Allows to configure a switch using RPi GPIO."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

from smbus2 import SMBus  # pylint: disable=import-error
from smbus2 import i2c_msg  # pylint: disable=import-error

_LOGGER = logging.getLogger(__name__)

CONF_PINS = "pins"
CONF_INVERT_LOGIC = "invert_logic"
CONF_I2CBUS = "i2c_bus"
CONF_I2CADDR = "i2c_address"
CONF_BITS = "bits"

DEFAULT_INVERT_LOGIC = False
DEFAULT_BITS = 24
_I2C_ADDR = 0x20

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Required(CONF_I2CBUS): cv.positive_int,
        vol.Optional(CONF_I2CADDR, default=_I2C_ADDR): cv.positive_int,
        vol.Optional(CONF_BITS, default=DEFAULT_BITS): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)

# Default value per 8-bits port
_PORT_VALUE = [0xFF]
_bus = None


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the swiches devices."""
    global _PORT_VALUE
    global _I2C_ADDR
    global _bus
    invert_logic = config.get(CONF_INVERT_LOGIC)
    switches = []
    pins = config.get(CONF_PINS)
    bits = config.get(CONF_BITS)
    _I2C_ADDR = config.get(CONF_I2CADDR)
    # Make 8-bits (can be 2- or 4-bits, but should always pack in a 8-bit msg)
    while bits % 8:
        bits += 1
        # Increase array size
    _PORT_VALUE *= int(bits / 8)
    # Set up I2C bus connectivity
    _bus = SMBus(config.get(CONF_I2CBUS))
    for pin, name in pins.items():
        switches.append(pi4ioe5v9Switch(name, pin, invert_logic))
    add_entities(switches)


def write_mem(pin, value):
    """Write a value to the IO expander."""
    global _PORT_VALUE
    byte_nr = int((pin - 1) / 8)
    bit_nr = int((pin - 1) - (byte_nr * 8))
    if byte_nr < len(_PORT_VALUE):
        mask = 0x1 << bit_nr
        # First remove the bit
        _PORT_VALUE[byte_nr] &= ~mask
        # If value set the correponding bit
        if value:
            _PORT_VALUE[byte_nr] |= mask
    else:
        _LOGGER.error(
            "Writing pin %d to  bit %d of port %d while IO-expander has only %d ports (%d bits)!",
            pin,
            bit_nr,
            byte_nr,
            len(_PORT_VALUE),
            len(_PORT_VALUE) * 8,
        )


def write_output():
    """Write memory content to hardware"""
    global _bus
    global _PORT_VALUE
    global _I2C_ADDR
    msg = i2c_msg.write(_I2C_ADDR, _PORT_VALUE)
    if _bus:
        _bus.i2c_rdwr(msg)
    else:
        _LOGGER.error("I2C bus not available!!")


class pi4ioe5v9Switch(ToggleEntity):
    """Representation of a  pi4ioe5v9 IO expansion IO."""

    def __init__(self, name, pin, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._invert_logic = invert_logic
        self._state = False
        write_mem(self._pin, 1 if self._invert_logic else 0)

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

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        write_mem(self._pin, 0 if self._invert_logic else 1)
        write_output()
        self._state = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        write_mem(self._pin, 1 if self._invert_logic else 0)
        write_output()
        self._state = False
        self.schedule_update_ha_state()
