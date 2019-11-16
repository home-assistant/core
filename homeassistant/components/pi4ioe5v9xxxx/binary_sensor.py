"""Support for binary sensor using RPi GPIO."""
import logging

import voluptuous as vol

from homeassistant.components import pi4ioe5v9xxxx
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
import binascii

from smbus2 import SMBus  # pylint: disable=import-error
from smbus2 import i2c_msg  # pylint: disable=import-error

_LOGGER = logging.getLogger(__name__)

CONF_INVERT_LOGIC = "invert_logic"
CONF_PINS = "pins"
CONF_I2CBUS = "i2c_bus"
CONF_I2CADDR = "i2c_address"
CONF_BITS = "bits"

DEFAULT_INVERT_LOGIC = False
DEFAULT_BITS = 24
_I2C_ADDR = 0x20


_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SENSORS_SCHEMA,
        vol.Required(CONF_I2CBUS): cv.positive_int,
        vol.Optional(CONF_I2CADDR, default=_I2C_ADDR): cv.positive_int,
        vol.Optional(CONF_BITS, default=DEFAULT_BITS): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)

_PORT_VALUE = [0xFF]
_bus = None


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IO expander devices."""
    global _PORT_VALUE
    global _I2C_ADDR
    global _bus
    invert_logic = config.get(CONF_INVERT_LOGIC)
    binary_sensors = []
    pins = config.get("pins")
    bits = config.get(CONF_BITS)
    _I2C_ADDR = config.get(CONF_I2CADDR)
    # Make 8-bits (can be 2- or 4-bits, but should always pack in a 8-bit msg)
    while bits % 8:
        bits += 1
    # Increase array size
    _PORT_VALUE *= int(bits / 8)
    # Set up I2C bus connectivity
    _bus = SMBus(config.get(CONF_I2CBUS))
    # Write 1 to all pins to prepaire them for reading
    msg = i2c_msg.write(_I2C_ADDR, _PORT_VALUE)
    if _bus:
        _bus.i2c_rdwr(msg)
    else:
        _LOGGER.error("I2C bus %d not available!!", config.get(CONF_I2CBUS))
    for pin_num, pin_name in pins.items():
        binary_sensors.append(pi4ioe5v9BinarySensor(pin_name, pin_num, invert_logic))
    add_entities(binary_sensors, True)


def read_data(pin):
    global _bus
    global _PORT_VALUE
    global _I2C_ADDR
    msg = i2c_msg.read(_I2C_ADDR, len(_PORT_VALUE))
    if _bus:
        _bus.i2c_rdwr(msg)
        for k in range(msg.len):
            _PORT_VALUE[k] = int(msg.buf[k].hex(), 16)
    else:
        _LOGGER.error("I2C bus %s not available!", config.get(CONF_I2CBUS))
    byte_nr = int((pin - 1) / 8)
    bit_nr = int((pin - 1) - (byte_nr * 8))
    mask = 0x01 << bit_nr
    if _PORT_VALUE[byte_nr] & mask:
        return True
    else:
        return False


class pi4ioe5v9BinarySensor(BinarySensorDevice):
    """Represent a binary sensor that uses pi4ioe5v9xxxx IO expander in read mode."""

    def __init__(self, name, pin, invert_logic):
        """Initialize the pi4ioe5v9xxxx sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._invert_logic = invert_logic
        self._state = read_data(self._pin)

    @property
    def should_poll(self):
        """No polling needed."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    def update(self):
        """Update the IO state."""
        self._state = read_data(self._pin)
