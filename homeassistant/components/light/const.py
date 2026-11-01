"""Provides constants for lights."""

from datetime import timedelta
from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

import probatio

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import LightEntity, Profiles

DOMAIN: Final = "light"
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


# Color mode of the light
ATTR_COLOR_MODE = "color_mode"
# List of color modes supported by the light
ATTR_SUPPORTED_COLOR_MODES = "supported_color_modes"

# Float that represents transition time in seconds to make change.
ATTR_TRANSITION = "transition"

# Lists holding color values
ATTR_RGB_COLOR = "rgb_color"
ATTR_RGBW_COLOR = "rgbw_color"
ATTR_RGBWW_COLOR = "rgbww_color"
ATTR_XY_COLOR = "xy_color"
ATTR_HS_COLOR = "hs_color"
ATTR_COLOR_TEMP_KELVIN = "color_temp_kelvin"
ATTR_MIN_COLOR_TEMP_KELVIN = "min_color_temp_kelvin"
ATTR_MAX_COLOR_TEMP_KELVIN = "max_color_temp_kelvin"
ATTR_COLOR_NAME = "color_name"
ATTR_WHITE = "white"

# Brightness of the light, 0..255 or percentage
ATTR_BRIGHTNESS = "brightness"
ATTR_BRIGHTNESS_PCT = "brightness_pct"
ATTR_BRIGHTNESS_STEP = "brightness_step"
ATTR_BRIGHTNESS_STEP_PCT = "brightness_step_pct"

# String representing a profile (built-in ones or external defined).
ATTR_PROFILE = "profile"

# If the light should flash, can be FLASH_SHORT or FLASH_LONG.
ATTR_FLASH = "flash"
FLASH_SHORT = "short"
FLASH_LONG = "long"

# List of possible effects
ATTR_EFFECT_LIST = "effect_list"

# Apply an effect to the light, can be EFFECT_COLORLOOP.
ATTR_EFFECT = "effect"
EFFECT_COLORLOOP = "colorloop"
EFFECT_OFF = "off"
EFFECT_RANDOM = "random"
EFFECT_WHITE = "white"

COLOR_GROUP = "Color descriptors"

LIGHT_PROFILES_FILE = "light_profiles.csv"

# Service call validation schemas
VALID_TRANSITION = probatio.All(probatio.Coerce(float), probatio.Clamp(min=0, max=6553))
VALID_BRIGHTNESS = probatio.All(probatio.Coerce(int), probatio.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = probatio.All(
    probatio.Coerce(float), probatio.Range(min=0, max=100)
)
VALID_BRIGHTNESS_STEP = probatio.All(
    probatio.Coerce(int), probatio.Clamp(min=-255, max=255)
)
VALID_BRIGHTNESS_STEP_PCT = probatio.All(
    probatio.Coerce(float), probatio.Clamp(min=-100, max=100)
)
VALID_FLASH = probatio.In([FLASH_SHORT, FLASH_LONG])

LIGHT_TURN_ON_SCHEMA: VolDictType = {
    probatio.Exclusive(ATTR_PROFILE, COLOR_GROUP): cv.string,
    ATTR_TRANSITION: VALID_TRANSITION,
    probatio.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
    probatio.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
    probatio.Exclusive(ATTR_BRIGHTNESS_STEP, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_STEP,
    probatio.Exclusive(
        ATTR_BRIGHTNESS_STEP_PCT, ATTR_BRIGHTNESS
    ): VALID_BRIGHTNESS_STEP_PCT,
    probatio.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
    probatio.Exclusive(ATTR_COLOR_TEMP_KELVIN, COLOR_GROUP): cv.positive_int,
    probatio.Exclusive(ATTR_HS_COLOR, COLOR_GROUP): probatio.All(
        probatio.Coerce(tuple),
        probatio.ExactSequence(
            (
                probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=360)),
                probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=100)),
            )
        ),
    ),
    probatio.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 3)
    ),
    probatio.Exclusive(ATTR_RGBW_COLOR, COLOR_GROUP): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 4)
    ),
    probatio.Exclusive(ATTR_RGBWW_COLOR, COLOR_GROUP): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 5)
    ),
    probatio.Exclusive(ATTR_XY_COLOR, COLOR_GROUP): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.small_float, cv.small_float))
    ),
    probatio.Exclusive(ATTR_WHITE, COLOR_GROUP): probatio.Any(True, VALID_BRIGHTNESS),
    ATTR_FLASH: VALID_FLASH,
    ATTR_EFFECT: cv.string,
}

LIGHT_TURN_OFF_SCHEMA: VolDictType = {
    ATTR_TRANSITION: VALID_TRANSITION,
    ATTR_FLASH: VALID_FLASH,
}
