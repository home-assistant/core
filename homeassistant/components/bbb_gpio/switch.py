"""Allows to configure a switch using BeagleBone Black GPIO."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import bbb_gpio
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_NAME, DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_PINS = "pins"
CONF_INITIAL = "initial"
CONF_INVERT_LOGIC = "invert_logic"

PIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_INITIAL, default=False): cv.boolean,
        vol.Optional(CONF_INVERT_LOGIC, default=False): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PINS, default={}): vol.Schema({cv.string: PIN_SCHEMA})}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the BeagleBone Black GPIO devices."""
    pins = config[CONF_PINS]

    switches = []
    for pin, params in pins.items():
        switches.append(BBBGPIOSwitch(pin, params))
    add_entities(switches)


class BBBGPIOSwitch(SwitchEntity):
    """Representation of a BeagleBone Black GPIO."""

    _attr_should_poll = False

    def __init__(self, pin, params):
        """Initialize the pin."""
        self._pin = pin
        self._attr_name = params[CONF_NAME] or DEVICE_DEFAULT_NAME
        self._state = params[CONF_INITIAL]
        self._invert_logic = params[CONF_INVERT_LOGIC]

        bbb_gpio.setup_output(self._pin)

        if self._state is False:
            bbb_gpio.write_output(self._pin, 1 if self._invert_logic else 0)
        else:
            bbb_gpio.write_output(self._pin, 0 if self._invert_logic else 1)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        bbb_gpio.write_output(self._pin, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        bbb_gpio.write_output(self._pin, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
