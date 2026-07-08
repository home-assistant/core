"""Provides constants for lights."""

from datetime import timedelta
from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import LightEntity, Profiles

DOMAIN = "light"
DATA_COMPONENT: HassKey[EntityComponent[LightEntity]] = HassKey(DOMAIN)
SCAN_INTERVAL = timedelta(seconds=30)

DATA_PROFILES: HassKey[Profiles] = HassKey(f"{DOMAIN}_profiles")


class LightEntityCapabilityAttribute(StrEnum):
    """Capability attributes for light entities."""

    MIN_COLOR_TEMP_KELVIN = "min_color_temp_kelvin"
    MAX_COLOR_TEMP_KELVIN = "max_color_temp_kelvin"
    EFFECT_LIST = "effect_list"
    SUPPORTED_COLOR_MODES = "supported_color_modes"


class LightEntityStateAttribute(StrEnum):
    """State attributes for light entities."""

    EFFECT = "effect"
    COLOR_MODE = "color_mode"
    BRIGHTNESS = "brightness"
    COLOR_TEMP_KELVIN = "color_temp_kelvin"
    HS_COLOR = "hs_color"
    RGB_COLOR = "rgb_color"
    XY_COLOR = "xy_color"
    RGBW_COLOR = "rgbw_color"
    RGBWW_COLOR = "rgbww_color"


class LightEntityFeature(IntFlag):
    """Supported features of the light entity."""

    EFFECT = 4
    FLASH = 8
    TRANSITION = 32


class ColorMode(StrEnum):
    """Possible light color modes."""

    UNKNOWN = "unknown"
    """Ambiguous color mode"""
    ONOFF = "onoff"
    """Must be the only supported mode"""
    BRIGHTNESS = "brightness"
    """Must be the only supported mode"""
    COLOR_TEMP = "color_temp"
    HS = "hs"
    XY = "xy"
    RGB = "rgb"
    RGBW = "rgbw"
    RGBWW = "rgbww"
    WHITE = "white"
    """Must *NOT* be the only supported mode"""


VALID_COLOR_MODES = {
    ColorMode.ONOFF,
    ColorMode.BRIGHTNESS,
    ColorMode.COLOR_TEMP,
    ColorMode.HS,
    ColorMode.XY,
    ColorMode.RGB,
    ColorMode.RGBW,
    ColorMode.RGBWW,
    ColorMode.WHITE,
}
COLOR_MODES_BRIGHTNESS = VALID_COLOR_MODES - {ColorMode.ONOFF}
COLOR_MODES_COLOR = {
    ColorMode.HS,
    ColorMode.RGB,
    ColorMode.RGBW,
    ColorMode.RGBWW,
    ColorMode.XY,
}

# Default to the Philips Hue value that HA has always assumed
# https://developers.meethue.com/documentation/core-concepts
DEFAULT_MIN_KELVIN = 2000  # 500 mireds
DEFAULT_MAX_KELVIN = 6535  # 153 mireds
