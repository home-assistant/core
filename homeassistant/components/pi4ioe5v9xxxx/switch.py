"""Allows to configure a switch using RPi GPIO."""
from __future__ import annotations

import logging

from pi4ioe5v9xxxx import pi4ioe5v9xxxx
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_PINS = "pins"
CONF_INVERT_LOGIC = "invert_logic"
CONF_I2CBUS = "i2c_bus"
CONF_I2CADDR = "i2c_address"
CONF_BITS = "bits"

DEFAULT_INVERT_LOGIC = False
DEFAULT_BITS = 24
DEFAULT_BUS = 1
DEFAULT_ADDR = 0x20

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_I2CBUS, default=DEFAULT_BUS): cv.positive_int,
        vol.Optional(CONF_I2CADDR, default=DEFAULT_ADDR): cv.positive_int,
        vol.Optional(CONF_BITS, default=DEFAULT_BITS): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the swiches devices."""
    _LOGGER.warning(
        "The pi4ioe5v9xxxx IO Expander integration is deprecated and will be removed "
        "in Home Assistant Core 2022.4; this integration is removed under "
        "Architectural Decision Record 0019, more information can be found here: "
        "https://github.com/home-assistant/architecture/blob/master/adr/0019-GPIO.md"
    )

    pins = config[CONF_PINS]
    switches = []

    pi4ioe5v9xxxx.setup(
        i2c_bus=config[CONF_I2CBUS],
        i2c_addr=config[CONF_I2CADDR],
        bits=config[CONF_BITS],
        read_mode=False,
        invert=False,
    )
    for pin, name in pins.items():
        switches.append(Pi4ioe5v9Switch(name, pin, config[CONF_INVERT_LOGIC]))
    add_entities(switches)


class Pi4ioe5v9Switch(SwitchEntity):
    """Representation of a  pi4ioe5v9 IO expansion IO."""

    def __init__(self, name, pin, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._invert_logic = invert_logic
        self._state = not invert_logic

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
        pi4ioe5v9xxxx.pin_to_memory(self._pin, not self._invert_logic)
        pi4ioe5v9xxxx.memory_to_hw()
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        pi4ioe5v9xxxx.pin_to_memory(self._pin, self._invert_logic)
        pi4ioe5v9xxxx.memory_to_hw()
        self._state = False
        self.schedule_update_ha_state()
