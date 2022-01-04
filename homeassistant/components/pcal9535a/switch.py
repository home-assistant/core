"""Support for switch sensor using I2C PCAL9535A chip."""
from __future__ import annotations

import logging

from pcal9535a import PCAL9535A
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_INVERT_LOGIC = "invert_logic"
CONF_I2C_ADDRESS = "i2c_address"
CONF_I2C_BUS = "i2c_bus"
CONF_PINS = "pins"
CONF_STRENGTH = "strength"

STRENGTH_025 = "0.25"
STRENGTH_050 = "0.5"
STRENGTH_075 = "0.75"
STRENGTH_100 = "1.0"

DEFAULT_INVERT_LOGIC = False
DEFAULT_I2C_ADDRESS = 0x20
DEFAULT_I2C_BUS = 1
DEFAULT_STRENGTH = STRENGTH_100

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_STRENGTH, default=DEFAULT_STRENGTH): vol.In(
            [STRENGTH_025, STRENGTH_050, STRENGTH_075, STRENGTH_100]
        ),
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): cv.positive_int,
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PCAL9535A devices."""
    _LOGGER.warning(
        "The PCAL9535A I/O Expander integration is deprecated and will be removed "
        "in Home Assistant Core 2022.4; this integration is removed under "
        "Architectural Decision Record 0019, more information can be found here: "
        "https://github.com/home-assistant/architecture/blob/master/adr/0019-GPIO.md"
    )

    invert_logic = config[CONF_INVERT_LOGIC]
    i2c_address = config[CONF_I2C_ADDRESS]
    bus = config[CONF_I2C_BUS]

    pcal = PCAL9535A(bus, i2c_address)

    switches = []
    pins = config[CONF_PINS]
    for pin_num, pin_name in pins.items():
        pin = pcal.get_pin(pin_num // 8, pin_num % 8)
        switches.append(PCAL9535ASwitch(pin_name, pin, invert_logic))

    add_entities(switches)


class PCAL9535ASwitch(SwitchEntity):
    """Representation of a PCAL9535A output pin."""

    def __init__(self, name, pin, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._pin.inverted = invert_logic
        self._pin.input = False
        self._state = self._pin.level

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
        self._pin.level = True
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._pin.level = False
        self._state = False
        self.schedule_update_ha_state()
