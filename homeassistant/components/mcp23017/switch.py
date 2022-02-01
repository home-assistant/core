"""Support for switch sensor using I2C MCP23017 chip."""
from __future__ import annotations

import logging

from adafruit_mcp230xx.mcp23017 import MCP23017
import board
import busio
import digitalio
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_INVERT_LOGIC = "invert_logic"
CONF_I2C_ADDRESS = "i2c_address"
CONF_PINS = "pins"
CONF_PULL_MODE = "pull_mode"

DEFAULT_INVERT_LOGIC = False
DEFAULT_I2C_ADDRESS = 0x20

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MCP23017 devices."""
    _LOGGER.warning(
        "The MCP23017 I/O Expander integration is deprecated and will be removed "
        "in Home Assistant Core 2022.4; this integration is removed under "
        "Architectural Decision Record 0019, more information can be found here: "
        "https://github.com/home-assistant/architecture/blob/master/adr/0019-GPIO.md"
    )
    invert_logic = config.get(CONF_INVERT_LOGIC)
    i2c_address = config.get(CONF_I2C_ADDRESS)

    i2c = busio.I2C(board.SCL, board.SDA)
    mcp = MCP23017(i2c, address=i2c_address)

    switches = []
    pins = config[CONF_PINS]
    for pin_num, pin_name in pins.items():
        pin = mcp.get_pin(pin_num)
        switches.append(MCP23017Switch(pin_name, pin, invert_logic))
    add_entities(switches)


class MCP23017Switch(SwitchEntity):
    """Representation of a  MCP23017 output pin."""

    def __init__(self, name, pin, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._invert_logic = invert_logic
        self._state = False

        self._pin.direction = digitalio.Direction.OUTPUT
        self._pin.value = self._invert_logic

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
        self._pin.value = not self._invert_logic
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._pin.value = self._invert_logic
        self._state = False
        self.schedule_update_ha_state()
