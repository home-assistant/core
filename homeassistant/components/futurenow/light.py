"""Support for FutureNow Ethernet unit outputs as Lights."""

from __future__ import annotations

from typing import Any

import pyfnip
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_DRIVER = "driver"
CONF_DRIVER_FNIP6X10AD = "FNIP6x10ad"
CONF_DRIVER_FNIP8X10A = "FNIP8x10a"
CONF_DRIVER_TYPES = [CONF_DRIVER_FNIP6X10AD, CONF_DRIVER_FNIP8X10A]

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional("dimmable", default=False): cv.boolean,
    }
)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DRIVER): vol.In(CONF_DRIVER_TYPES),
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_DEVICES): {cv.string: DEVICE_SCHEMA},
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform for each FutureNow unit."""
    lights = []
    for channel, device_config in config[CONF_DEVICES].items():
        device = {}
        device["name"] = device_config[CONF_NAME]
        device["dimmable"] = device_config["dimmable"]
        device["channel"] = channel
        device["driver"] = config[CONF_DRIVER]
        device["host"] = config[CONF_HOST]
        device["port"] = config[CONF_PORT]
        lights.append(FutureNowLight(device))

    add_entities(lights, True)


def to_futurenow_level(level):
    """Convert the given Home Assistant light level (0-255) to FutureNow (0-100)."""
    return round((level * 100) / 255)


def to_hass_level(level):
    """Convert the given FutureNow (0-100) light level to Home Assistant (0-255)."""
    return int((level * 255) / 100)


class FutureNowLight(LightEntity):
    """Representation of an FutureNow light."""

    def __init__(self, device):
        """Initialize the light."""
        self._name = device["name"]
        self._dimmable = device["dimmable"]
        self._channel = device["channel"]
        self._brightness = None
        self._last_brightness = 255
        self._state = None

        if device["driver"] == CONF_DRIVER_FNIP6X10AD:
            self._light = pyfnip.FNIP6x2adOutput(
                device["host"], device["port"], self._channel
            )
        if device["driver"] == CONF_DRIVER_FNIP8X10A:
            self._light = pyfnip.FNIP8x10aOutput(
                device["host"], device["port"], self._channel
            )

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._dimmable:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if self._dimmable:
            level = kwargs.get(ATTR_BRIGHTNESS, self._last_brightness)
        else:
            level = 255
        self._light.turn_on(to_futurenow_level(level))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._light.turn_off()
        if self._brightness:
            self._last_brightness = self._brightness

    def update(self) -> None:
        """Fetch new state data for this light."""
        state = int(self._light.is_on())
        self._state = bool(state)
        self._brightness = to_hass_level(state)
