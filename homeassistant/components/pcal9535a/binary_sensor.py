"""Support for binary sensor using I2C PCAL9535A chip."""
import logging

from pcal9535a import PCAL9535A
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_INVERT_LOGIC = "invert_logic"
CONF_I2C_ADDRESS = "i2c_address"
CONF_I2C_BUS = "i2c_bus"
CONF_PINS = "pins"
CONF_PULL_MODE = "pull_mode"

MODE_UP = "UP"
MODE_DOWN = "DOWN"
MODE_DISABLED = "DISABLED"

DEFAULT_INVERT_LOGIC = False
DEFAULT_I2C_ADDRESS = 0x20
DEFAULT_I2C_BUS = 1
DEFAULT_PULL_MODE = MODE_DISABLED

_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SENSORS_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): vol.All(
            vol.Upper, vol.In([MODE_UP, MODE_DOWN, MODE_DISABLED])
        ),
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PCAL9535A binary sensors."""
    pull_mode = config[CONF_PULL_MODE]
    invert_logic = config[CONF_INVERT_LOGIC]
    i2c_address = config[CONF_I2C_ADDRESS]
    bus = config[CONF_I2C_BUS]

    pcal = PCAL9535A(bus, i2c_address)

    binary_sensors = []
    pins = config[CONF_PINS]

    for pin_num, pin_name in pins.items():
        pin = pcal.get_pin(pin_num // 8, pin_num % 8)
        binary_sensors.append(
            PCAL9535ABinarySensor(pin_name, pin, pull_mode, invert_logic)
        )

    add_entities(binary_sensors, True)


class PCAL9535ABinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses PCAL9535A."""

    def __init__(self, name, pin, pull_mode, invert_logic):
        """Initialize the PCAL9535A binary sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._pin.input = True
        self._pin.inverted = invert_logic
        if pull_mode == "DISABLED":
            self._pin.pullup = 0
        elif pull_mode == "DOWN":
            self._pin.pullup = -1
        else:
            self._pin.pullup = 1
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the cached state of the entity."""
        return self._state

    def update(self):
        """Update the GPIO state."""
        self._state = self._pin.level
