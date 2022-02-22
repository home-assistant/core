"""Support for binary sensor using RPi GPIO."""
from __future__ import annotations

import logging

from pi4ioe5v9xxxx import pi4ioe5v9xxxx
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_INVERT_LOGIC = "invert_logic"
CONF_PINS = "pins"
CONF_I2CBUS = "i2c_bus"
CONF_I2CADDR = "i2c_address"
CONF_BITS = "bits"

DEFAULT_INVERT_LOGIC = False
DEFAULT_BITS = 24
DEFAULT_BUS = 1
DEFAULT_ADDR = 0x20


_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SENSORS_SCHEMA,
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
    """Set up the IO expander devices."""
    _LOGGER.warning(
        "The pi4ioe5v9xxxx IO Expander integration is deprecated and will be removed "
        "in Home Assistant Core 2022.4; this integration is removed under "
        "Architectural Decision Record 0019, more information can be found here: "
        "https://github.com/home-assistant/architecture/blob/master/adr/0019-GPIO.md"
    )

    pins = config[CONF_PINS]
    binary_sensors = []

    pi4ioe5v9xxxx.setup(
        i2c_bus=config[CONF_I2CBUS],
        i2c_addr=config[CONF_I2CADDR],
        bits=config[CONF_BITS],
        read_mode=True,
        invert=False,
    )
    for pin_num, pin_name in pins.items():
        binary_sensors.append(
            Pi4ioe5v9BinarySensor(pin_name, pin_num, config[CONF_INVERT_LOGIC])
        )
    add_entities(binary_sensors, True)


class Pi4ioe5v9BinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses pi4ioe5v9xxxx IO expander in read mode."""

    def __init__(self, name, pin, invert_logic):
        """Initialize the pi4ioe5v9xxxx sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._invert_logic = invert_logic
        self._state = pi4ioe5v9xxxx.pin_from_memory(self._pin)

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
        pi4ioe5v9xxxx.hw_to_memory()
        self._state = pi4ioe5v9xxxx.pin_from_memory(self._pin)
