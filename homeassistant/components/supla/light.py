"""Support for Supla lights - dimmer and rgbw"""
from __future__ import annotations

import logging
from pprint import pformat
from typing import Any

from math import ceil

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

from . import DOMAIN, SUPLA_COORDINATORS, SUPLA_SERVERS, SuplaChannel

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
                SuplaDimmer(
                    device,
                    hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                    hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
                )
            )

        elif device_name == SUPLA_RGBLIGHTING:
            entities.append(
                SuplaRGBLighting(
                    device,
                    hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                    hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
                )
            )

    async_add_entities(entities)


class SuplaDimmer(SuplaChannel, LightEntity):
    """Representation of a Supla dimmable light."""

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

    @property
    def color_mode(self) -> str | None:
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[str] | None:
        return {ColorMode.BRIGHTNESS}


class SuplaRGBLighting(SuplaChannel, LightEntity):
    """Representation of a Supla RGB light."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        hs_color = kwargs.get(ATTR_HS_COLOR) or self.hs_color
        brightness = (kwargs.get(ATTR_BRIGHTNESS) or self.brightness) / 255.0 * 100
        if hs_color and brightness:
            rgb_update_color = color_util.color_hsv_to_RGB(
                hs_color[0], hs_color[1], brightness
            )
            (r, g, b) = rgb_update_color
            # Color is set as the hex string of the form "0xRRGGBB"
            color = "0x" + color_util.color_rgb_to_hex(r, g, b)
            await self.async_action("SET_RGBW_PARAMETERS", color=color)
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
        if not state or "color_brightness" not in state:
            return None
        brightness = state.get("color_brightness")
        # Convert from (0-100) to Home Assistant brightness (0-255)
        return min(255, ceil(brightness * 255 / 100.0))

    @property
    def hs_color(self) -> tuple[float, float] | None:
        state = self.channel_data.get("state")
        if not state or "color" not in state:
            return None
        # Color is defined as the hex string of the form "0xRRGGBB",
        # so last 6 chars are extracted from it to remove the prefix.
        hex_color = state.get("color")[-6:]
        rgb_color = color_util.rgb_hex_to_rgb_list(hex_color)
        return color_util.color_RGB_to_hs(rgb_color[0], rgb_color[1], rgb_color[2])

    @property
    def color_mode(self) -> str | None:
        return ColorMode.HS

    @property
    def supported_color_modes(self) -> set[str] | None:
        return {ColorMode.HS}
