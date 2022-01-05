"""Support for binary sensor using I2C MCP23017 chip."""
from __future__ import annotations

import logging

from adafruit_mcp230xx.mcp23017 import MCP23017
import board
import busio
import digitalio
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_INVERT_LOGIC = "invert_logic"
CONF_I2C_ADDRESS = "i2c_address"
CONF_PINS = "pins"
CONF_PULL_MODE = "pull_mode"

MODE_UP = "UP"
MODE_DOWN = "DOWN"

DEFAULT_INVERT_LOGIC = False
DEFAULT_I2C_ADDRESS = 0x20
DEFAULT_PULL_MODE = MODE_UP

_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SENSORS_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): vol.All(
            vol.Upper, vol.In([MODE_UP, MODE_DOWN])
        ),
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MCP23017 binary sensors."""
    _LOGGER.warning(
        "The MCP23017 I/O Expander integration is deprecated and will be removed "
        "in Home Assistant Core 2022.4; this integration is removed under "
        "Architectural Decision Record 0019, more information can be found here: "
        "https://github.com/home-assistant/architecture/blob/master/adr/0019-GPIO.md"
    )
    pull_mode = config[CONF_PULL_MODE]
    invert_logic = config[CONF_INVERT_LOGIC]
    i2c_address = config[CONF_I2C_ADDRESS]

    i2c = busio.I2C(board.SCL, board.SDA)
    mcp = MCP23017(i2c, address=i2c_address)

    binary_sensors = []
    pins = config[CONF_PINS]

    for pin_num, pin_name in pins.items():
        pin = mcp.get_pin(pin_num)
        binary_sensors.append(
            MCP23017BinarySensor(pin_name, pin, pull_mode, invert_logic)
        )

    add_devices(binary_sensors, True)


class MCP23017BinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses MCP23017."""

    def __init__(self, name, pin, pull_mode, invert_logic):
        """Initialize the MCP23017 binary sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._pull_mode = pull_mode
        self._invert_logic = invert_logic
        self._state = None
        self._pin.direction = digitalio.Direction.INPUT
        self._pin.pull = digitalio.Pull.UP

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    def update(self):
        """Update the GPIO state."""
        self._state = self._pin.value
