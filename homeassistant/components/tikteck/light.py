"""Support for Tikteck lights."""

from __future__ import annotations

import logging
from typing import Any

import tikteck
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import color as color_util

_LOGGER = logging.getLogger(__name__)

DEVICE_SCHEMA = vol.Schema(
    {vol.Optional(CONF_NAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tikteck platform."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        device = {}
        device["name"] = device_config[CONF_NAME]
        device["password"] = device_config[CONF_PASSWORD]
        device["address"] = address
        light = TikteckLight(device)
        if light.is_valid:
            lights.append(light)

    add_entities(lights)


class TikteckLight(LightEntity):
    """Representation of a Tikteck light."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.HS
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.HS}
    hs_color: tuple[float, float]
    brightness: int

    def __init__(self, device):
        """Initialize the light."""

        address = device["address"]
        self._attr_unique_id = address
        self._attr_name = device["name"]
        self._attr_brightness = 255
        self._attr_hs_color = [0, 0]
        self._attr_is_on = False
        self.is_valid = True
        self._bulb = tikteck.tikteck(address, "Smart Light", device["password"])
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error("Failed to connect to bulb %s, %s", address, self.name)

    def set_state(self, red: int, green: int, blue: int, brightness: int) -> bool:
        """Set the bulb state."""
        return self._bulb.set_state(red, green, blue, brightness)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the specified light on."""
        self._attr_is_on = True

        hs_color = kwargs.get(ATTR_HS_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if hs_color is not None:
            self._attr_hs_color = hs_color
        if brightness is not None:
            self._attr_brightness = brightness

        rgb = color_util.color_hs_to_RGB(self.hs_color[0], self.hs_color[1])

        self.set_state(rgb[0], rgb[1], rgb[2], self.brightness)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the specified light off."""
        self._attr_is_on = False
        self.set_state(0, 0, 0, 0)
        self.schedule_update_ha_state()
