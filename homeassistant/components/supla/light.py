"""Support for Supla lights - dimmer and rgb."""
from __future__ import annotations

import logging
from math import ceil
from pprint import pformat
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

from . import DOMAIN, SUPLA_COORDINATORS, SUPLA_SERVERS
from .entity import SuplaEntity

_LOGGER = logging.getLogger(__name__)

SUPLA_DIMMER = "DIMMER"
SUPLA_RGBLIGHTING = "RGBLIGHTING"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Supla lights."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    entities: list[LightEntity] = []
    for device in discovery_info.values():
        device_name = device["function_name"]
        server_name = device["server_name"]

        if device_name == SUPLA_DIMMER:
            entities.append(
                SuplaDimmerEntity(
                    device,
                    hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                    hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
                )
            )

        elif device_name == SUPLA_RGBLIGHTING:
            entities.append(
                SuplaRGBLightingEntity(
                    device,
                    hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                    hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
                )
            )

    async_add_entities(entities)


class SuplaDimmerEntity(SuplaEntity, LightEntity):
    """Representation of a Supla dimmable light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if ATTR_BRIGHTNESS in kwargs:
            # Convert from Home Assistant brightness (0-255) to (0-100)
            brightness = min(100, ceil(kwargs[ATTR_BRIGHTNESS] * 100 / 255.0))
            await self.async_action("SET_RGBW_PARAMETERS", brightness=brightness)
            return
        await self.async_action("TURN_ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.async_action("TURN_OFF")

    @property
    def is_on(self):
        """Return true if switch is on."""
        if state := self.channel_data.get("state"):
            return state["on"]
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        state = self.channel_data.get("state")
        if not state or "brightness" not in state:
            return None
        brightness = state.get("brightness")
        # Convert from (0-100) to Home Assistant brightness (0-255)
        return min(255, ceil(brightness * 255 / 100.0))


class SuplaRGBLightingEntity(SuplaEntity, LightEntity):
    """Representation of a Supla RGB light."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        brightness = kwargs.get(ATTR_BRIGHTNESS) or self.brightness
        hs_color = kwargs.get(ATTR_HS_COLOR) or self.hs_color
        if not self.is_on and ATTR_HS_COLOR in kwargs and ATTR_BRIGHTNESS not in kwargs:
            # When the light is off, brightness state is set to 0.
            # However, last color state is preserved, and we can extract last brightness from it.
            brightness = self._brightness_from_color

        if not kwargs or not (hs_color and brightness):
            await self.async_action("TURN_ON")
            return
        rgb_update_color = color_util.color_hsv_to_RGB(
            hs_color[0], hs_color[1], brightness / 255.0 * 100
        )
        (red, green, blue) = rgb_update_color
        # Color is set as the hex string of the form "0xRRGGBB"
        color = "0x" + color_util.color_rgb_to_hex(red, green, blue)
        await self.async_action("SET_RGBW_PARAMETERS", color=color)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.async_action("TURN_OFF")

    @property
    def is_on(self):
        """Return true if switch is on."""
        if state := self.channel_data.get("state"):
            return state["on"]
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        state = self.channel_data.get("state")
        if not state or "color_brightness" not in state:
            return None
        brightness = state.get("color_brightness")
        # Convert from (0-100) to Home Assistant brightness (0-255)
        return min(255, ceil(brightness * 255 / 100.0))

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value."""
        rgb_color = self._rgb_color_raw
        if not rgb_color:
            return None
        return color_util.color_RGB_to_hs(rgb_color[0], rgb_color[1], rgb_color[2])

    @property
    def _brightness_from_color(self) -> int | None:
        rgb_color = self._rgb_color_raw
        if not rgb_color:
            return None
        # Brightness is equal to max color intensity in range 0-255.
        return max(rgb_color)

    @property
    def _rgb_color_raw(self) -> list[int] | None:
        state = self.channel_data.get("state")
        if not state or "color" not in state:
            return None
        # Color is defined as the hex string of the form "0xRRGGBB",
        # so last 6 chars are extracted from it to remove the prefix.
        hex_color = state.get("color")[-6:]
        return color_util.rgb_hex_to_rgb_list(hex_color)
