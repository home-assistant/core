"""Provides functionality to interact with lights."""

from __future__ import annotations

from collections.abc import Iterable
import csv
import dataclasses
from functools import partial
import logging
import os
from typing import TYPE_CHECKING, Any, Final, Self, cast, final

from propcache.api import cached_property
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.frame import ReportBehavior, report_usage
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.loader import bind_hass
from homeassistant.util import color as color_util

from .const import (  # noqa: F401
    COLOR_MODES_BRIGHTNESS,
    COLOR_MODES_COLOR,
    DATA_COMPONENT,
    DATA_PROFILES,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DOMAIN,
    SCAN_INTERVAL,
    VALID_COLOR_MODES,
    ColorMode,
    LightEntityFeature,
)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the LightEntityFeature enum instead.
_DEPRECATED_SUPPORT_BRIGHTNESS: Final = DeprecatedConstant(
    1, "supported_color_modes", "2026.1"
)  # Deprecated, replaced by color modes
_DEPRECATED_SUPPORT_COLOR_TEMP: Final = DeprecatedConstant(
    2, "supported_color_modes", "2026.1"
)  # Deprecated, replaced by color modes
_DEPRECATED_SUPPORT_EFFECT: Final = DeprecatedConstantEnum(
    LightEntityFeature.EFFECT, "2026.1"
)
_DEPRECATED_SUPPORT_FLASH: Final = DeprecatedConstantEnum(
    LightEntityFeature.FLASH, "2026.1"
)
_DEPRECATED_SUPPORT_COLOR: Final = DeprecatedConstant(
    16, "supported_color_modes", "2026.1"
)  # Deprecated, replaced by color modes
_DEPRECATED_SUPPORT_TRANSITION: Final = DeprecatedConstantEnum(
    LightEntityFeature.TRANSITION, "2026.1"
)

# Color mode of the light
ATTR_COLOR_MODE = "color_mode"
# List of color modes supported by the light
ATTR_SUPPORTED_COLOR_MODES = "supported_color_modes"

# These COLOR_MODE_* constants are deprecated as of Home Assistant 2022.5.
# Please use the LightEntityFeature enum instead.
_DEPRECATED_COLOR_MODE_UNKNOWN: Final = DeprecatedConstantEnum(
    ColorMode.UNKNOWN, "2026.1"
)
_DEPRECATED_COLOR_MODE_ONOFF: Final = DeprecatedConstantEnum(ColorMode.ONOFF, "2026.1")
_DEPRECATED_COLOR_MODE_BRIGHTNESS: Final = DeprecatedConstantEnum(
    ColorMode.BRIGHTNESS, "2026.1"
)
_DEPRECATED_COLOR_MODE_COLOR_TEMP: Final = DeprecatedConstantEnum(
    ColorMode.COLOR_TEMP, "2026.1"
)
_DEPRECATED_COLOR_MODE_HS: Final = DeprecatedConstantEnum(ColorMode.HS, "2026.1")
_DEPRECATED_COLOR_MODE_XY: Final = DeprecatedConstantEnum(ColorMode.XY, "2026.1")
_DEPRECATED_COLOR_MODE_RGB: Final = DeprecatedConstantEnum(ColorMode.RGB, "2026.1")
_DEPRECATED_COLOR_MODE_RGBW: Final = DeprecatedConstantEnum(ColorMode.RGBW, "2026.1")
_DEPRECATED_COLOR_MODE_RGBWW: Final = DeprecatedConstantEnum(ColorMode.RGBWW, "2026.1")
_DEPRECATED_COLOR_MODE_WHITE: Final = DeprecatedConstantEnum(ColorMode.WHITE, "2026.1")


# mypy: disallow-any-generics


def filter_supported_color_modes(color_modes: Iterable[ColorMode]) -> set[ColorMode]:
    """Filter the given color modes."""
    color_modes = set(color_modes)
    if (
        not color_modes
        or ColorMode.UNKNOWN in color_modes
        or (ColorMode.WHITE in color_modes and not color_supported(color_modes))
    ):
        raise HomeAssistantError

    if ColorMode.ONOFF in color_modes and len(color_modes) > 1:
        color_modes.remove(ColorMode.ONOFF)
    if ColorMode.BRIGHTNESS in color_modes and len(color_modes) > 1:
        color_modes.remove(ColorMode.BRIGHTNESS)
    return color_modes


def valid_supported_color_modes(
    color_modes: Iterable[ColorMode | str],
) -> set[ColorMode | str]:
    """Validate the given color modes."""
    color_modes = set(color_modes)
    if (
        not color_modes
        or ColorMode.UNKNOWN in color_modes
        or (ColorMode.BRIGHTNESS in color_modes and len(color_modes) > 1)
        or (ColorMode.ONOFF in color_modes and len(color_modes) > 1)
        or (ColorMode.WHITE in color_modes and not color_supported(color_modes))
    ):
        raise vol.Error(f"Invalid supported_color_modes {sorted(color_modes)}")
    return color_modes


def brightness_supported(color_modes: Iterable[ColorMode | str] | None) -> bool:
    """Test if brightness is supported."""
    if not color_modes:
        return False
    return not COLOR_MODES_BRIGHTNESS.isdisjoint(color_modes)


def color_supported(color_modes: Iterable[ColorMode | str] | None) -> bool:
    """Test if color is supported."""
    if not color_modes:
        return False
    return not COLOR_MODES_COLOR.isdisjoint(color_modes)


def color_temp_supported(color_modes: Iterable[ColorMode | str] | None) -> bool:
    """Test if color temperature is supported."""
    if not color_modes:
        return False
    return ColorMode.COLOR_TEMP in color_modes


def get_supported_color_modes(hass: HomeAssistant, entity_id: str) -> set[str] | None:
    """Get supported color modes for a light entity.

    First try the statemachine, then entity registry.
    This is the equivalent of entity helper get_supported_features.
    """
    if state := hass.states.get(entity_id):
        return state.attributes.get(ATTR_SUPPORTED_COLOR_MODES)

    entity_registry = er.async_get(hass)
    if not (entry := entity_registry.async_get(entity_id)):
        raise HomeAssistantError(f"Unknown entity {entity_id}")
    if not entry.capabilities:
        return None

    return entry.capabilities.get(ATTR_SUPPORTED_COLOR_MODES)


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

# Deprecated in HA Core 2022.11
_DEPRECATED_ATTR_COLOR_TEMP: Final = DeprecatedConstant(
    "color_temp", "kelvin equivalent (ATTR_COLOR_TEMP_KELVIN)", "2026.1"
)
_DEPRECATED_ATTR_KELVIN: Final = DeprecatedConstant(
    "kelvin", "ATTR_COLOR_TEMP_KELVIN", "2026.1"
)
_DEPRECATED_ATTR_MIN_MIREDS: Final = DeprecatedConstant(
    "min_mireds", "kelvin equivalent (ATTR_MAX_COLOR_TEMP_KELVIN)", "2026.1"
)
_DEPRECATED_ATTR_MAX_MIREDS: Final = DeprecatedConstant(
    "max_mireds", "kelvin equivalent (ATTR_MIN_COLOR_TEMP_KELVIN)", "2026.1"
)

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
VALID_TRANSITION = vol.All(vol.Coerce(float), vol.Clamp(min=0, max=6553))
VALID_BRIGHTNESS = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
VALID_BRIGHTNESS_STEP = vol.All(vol.Coerce(int), vol.Clamp(min=-255, max=255))
VALID_BRIGHTNESS_STEP_PCT = vol.All(vol.Coerce(float), vol.Clamp(min=-100, max=100))
VALID_FLASH = vol.In([FLASH_SHORT, FLASH_LONG])

LIGHT_TURN_ON_SCHEMA: VolDictType = {
    vol.Exclusive(ATTR_PROFILE, COLOR_GROUP): cv.string,
    ATTR_TRANSITION: VALID_TRANSITION,
    vol.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
    vol.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
    vol.Exclusive(ATTR_BRIGHTNESS_STEP, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_STEP,
    vol.Exclusive(ATTR_BRIGHTNESS_STEP_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_STEP_PCT,
    vol.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
    vol.Exclusive(_DEPRECATED_ATTR_COLOR_TEMP.value, COLOR_GROUP): vol.All(
        vol.Coerce(int), vol.Range(min=1)
    ),
    vol.Exclusive(ATTR_COLOR_TEMP_KELVIN, COLOR_GROUP): cv.positive_int,
    vol.Exclusive(_DEPRECATED_ATTR_KELVIN.value, COLOR_GROUP): cv.positive_int,
    vol.Exclusive(ATTR_HS_COLOR, COLOR_GROUP): vol.All(
        vol.Coerce(tuple),
        vol.ExactSequence(
            (
                vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            )
        ),
    ),
    vol.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP): vol.All(
        vol.Coerce(tuple), vol.ExactSequence((cv.byte,) * 3)
    ),
    vol.Exclusive(ATTR_RGBW_COLOR, COLOR_GROUP): vol.All(
        vol.Coerce(tuple), vol.ExactSequence((cv.byte,) * 4)
    ),
    vol.Exclusive(ATTR_RGBWW_COLOR, COLOR_GROUP): vol.All(
        vol.Coerce(tuple), vol.ExactSequence((cv.byte,) * 5)
    ),
    vol.Exclusive(ATTR_XY_COLOR, COLOR_GROUP): vol.All(
        vol.Coerce(tuple), vol.ExactSequence((cv.small_float, cv.small_float))
    ),
    vol.Exclusive(ATTR_WHITE, COLOR_GROUP): vol.Any(True, VALID_BRIGHTNESS),
    ATTR_FLASH: VALID_FLASH,
    ATTR_EFFECT: cv.string,
}

LIGHT_TURN_OFF_SCHEMA: VolDictType = {
    ATTR_TRANSITION: VALID_TRANSITION,
    ATTR_FLASH: VALID_FLASH,
}


_LOGGER = logging.getLogger(__name__)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the lights are on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


def preprocess_turn_on_alternatives(
    hass: HomeAssistant, params: dict[str, Any]
) -> None:
    """Process extra data for turn light on request.

    Async friendly.
    """
    # Bail out, we process this later.
    if ATTR_BRIGHTNESS_STEP in params or ATTR_BRIGHTNESS_STEP_PCT in params:
        return

    if ATTR_PROFILE in params:
        hass.data[DATA_PROFILES].apply_profile(params.pop(ATTR_PROFILE), params)

    if (color_name := params.pop(ATTR_COLOR_NAME, None)) is not None:
        try:
            params[ATTR_RGB_COLOR] = color_util.color_name_to_rgb(color_name)
        except ValueError:
            _LOGGER.warning("Got unknown color %s, falling back to white", color_name)
            params[ATTR_RGB_COLOR] = (255, 255, 255)

    if (mired := params.pop(_DEPRECATED_ATTR_COLOR_TEMP.value, None)) is not None:
        _LOGGER.warning(
            "Got `color_temp` argument in `turn_on` service, which is deprecated "
            "and will break in Home Assistant 2026.1, please use "
            "`color_temp_kelvin` argument"
        )
        kelvin = color_util.color_temperature_mired_to_kelvin(mired)
        params[_DEPRECATED_ATTR_COLOR_TEMP.value] = int(mired)
        params[ATTR_COLOR_TEMP_KELVIN] = int(kelvin)

    if (kelvin := params.pop(_DEPRECATED_ATTR_KELVIN.value, None)) is not None:
        _LOGGER.warning(
            "Got `kelvin` argument in `turn_on` service, which is deprecated "
            "and will break in Home Assistant 2026.1, please use "
            "`color_temp_kelvin` argument"
        )
        mired = color_util.color_temperature_kelvin_to_mired(kelvin)
        params[_DEPRECATED_ATTR_COLOR_TEMP.value] = int(mired)
        params[ATTR_COLOR_TEMP_KELVIN] = int(kelvin)

    if (kelvin := params.pop(ATTR_COLOR_TEMP_KELVIN, None)) is not None:
        mired = color_util.color_temperature_kelvin_to_mired(kelvin)
        params[_DEPRECATED_ATTR_COLOR_TEMP.value] = int(mired)
        params[ATTR_COLOR_TEMP_KELVIN] = int(kelvin)

    brightness_pct = params.pop(ATTR_BRIGHTNESS_PCT, None)
    if brightness_pct is not None:
        params[ATTR_BRIGHTNESS] = round(255 * brightness_pct / 100)


def filter_turn_off_params(
    light: LightEntity, params: dict[str, Any]
) -> dict[str, Any]:
    """Filter out params not used in turn off or not supported by the light."""
    if not params:
        return params

    supported_features = light.supported_features_compat

    if LightEntityFeature.FLASH not in supported_features:
        params.pop(ATTR_FLASH, None)
    if LightEntityFeature.TRANSITION not in supported_features:
        params.pop(ATTR_TRANSITION, None)

    return {k: v for k, v in params.items() if k in (ATTR_TRANSITION, ATTR_FLASH)}


def filter_turn_on_params(light: LightEntity, params: dict[str, Any]) -> dict[str, Any]:
    """Filter out params not supported by the light."""
    supported_features = light.supported_features_compat

    if LightEntityFeature.EFFECT not in supported_features:
        params.pop(ATTR_EFFECT, None)
    if LightEntityFeature.FLASH not in supported_features:
        params.pop(ATTR_FLASH, None)
    if LightEntityFeature.TRANSITION not in supported_features:
        params.pop(ATTR_TRANSITION, None)

    supported_color_modes = (
        light._light_internal_supported_color_modes  # noqa: SLF001
    )
    if not brightness_supported(supported_color_modes):
        params.pop(ATTR_BRIGHTNESS, None)
    if ColorMode.COLOR_TEMP not in supported_color_modes:
        params.pop(_DEPRECATED_ATTR_COLOR_TEMP.value, None)
        params.pop(ATTR_COLOR_TEMP_KELVIN, None)
    if ColorMode.HS not in supported_color_modes:
        params.pop(ATTR_HS_COLOR, None)
    if ColorMode.RGB not in supported_color_modes:
        params.pop(ATTR_RGB_COLOR, None)
    if ColorMode.RGBW not in supported_color_modes:
        params.pop(ATTR_RGBW_COLOR, None)
    if ColorMode.RGBWW not in supported_color_modes:
        params.pop(ATTR_RGBWW_COLOR, None)
    if ColorMode.WHITE not in supported_color_modes:
        params.pop(ATTR_WHITE, None)
    if ColorMode.XY not in supported_color_modes:
        params.pop(ATTR_XY_COLOR, None)

    return params


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: C901
    """Expose light control via state machine and services."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[LightEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    profiles = hass.data[DATA_PROFILES] = Profiles(hass)
    # Profiles are loaded in a separate task to avoid delaying the setup
    # of the light base platform.
    hass.async_create_task(profiles.async_initialize(), eager_start=True)

    def preprocess_data(data: dict[str, Any]) -> VolDictType:
        """Preprocess the service data."""
        base: VolDictType = {
            entity_field: data.pop(entity_field)  # type: ignore[arg-type]
            for entity_field in cv.ENTITY_SERVICE_FIELDS
            if entity_field in data
        }

        preprocess_turn_on_alternatives(hass, data)
        base["params"] = data
        return base

    async def async_handle_light_on_service(  # noqa: C901
        light: LightEntity, call: ServiceCall
    ) -> None:
        """Handle turning a light on.

        If brightness is set to 0, this service will turn the light off.
        """
        params: dict[str, Any] = dict(call.data["params"])

        # Only process params once we processed brightness step
        if params and (
            ATTR_BRIGHTNESS_STEP in params or ATTR_BRIGHTNESS_STEP_PCT in params
        ):
            brightness = light.brightness if light.is_on and light.brightness else 0

            if ATTR_BRIGHTNESS_STEP in params:
                brightness += params.pop(ATTR_BRIGHTNESS_STEP)

            else:
                brightness += round(params.pop(ATTR_BRIGHTNESS_STEP_PCT) / 100 * 255)

            params[ATTR_BRIGHTNESS] = max(0, min(255, brightness))

            preprocess_turn_on_alternatives(hass, params)

        if (not params or not light.is_on) or (
            params and ATTR_TRANSITION not in params
        ):
            profiles.apply_default(light.entity_id, light.is_on, params)

        legacy_supported_color_modes = light._light_internal_supported_color_modes  # noqa: SLF001
        supported_color_modes = light.supported_color_modes

        # If a color temperature is specified, emulate it if not supported by the light
        if ATTR_COLOR_TEMP_KELVIN in params:
            if (
                supported_color_modes
                and ColorMode.COLOR_TEMP not in supported_color_modes
                and ColorMode.RGBWW in supported_color_modes
            ):
                params.pop(_DEPRECATED_ATTR_COLOR_TEMP.value)
                color_temp = params.pop(ATTR_COLOR_TEMP_KELVIN)
                brightness = cast(int, params.get(ATTR_BRIGHTNESS, light.brightness))
                params[ATTR_RGBWW_COLOR] = color_util.color_temperature_to_rgbww(
                    color_temp,
                    brightness,
                    light.min_color_temp_kelvin,
                    light.max_color_temp_kelvin,
                )
            elif ColorMode.COLOR_TEMP not in legacy_supported_color_modes:
                params.pop(_DEPRECATED_ATTR_COLOR_TEMP.value)
                color_temp = params.pop(ATTR_COLOR_TEMP_KELVIN)
                if color_supported(legacy_supported_color_modes):
                    params[ATTR_HS_COLOR] = color_util.color_temperature_to_hs(
                        color_temp
                    )

        # If a color is specified, convert to the color space supported by the light
        # Backwards compatibility: Fall back to hs color if light.supported_color_modes
        # is not implemented
        rgb_color: tuple[int, int, int] | None
        rgbww_color: tuple[int, int, int, int, int] | None
        if not supported_color_modes:
            if (rgb_color := params.pop(ATTR_RGB_COLOR, None)) is not None:
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            elif (xy_color := params.pop(ATTR_XY_COLOR, None)) is not None:
                params[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)
            elif (rgbw_color := params.pop(ATTR_RGBW_COLOR, None)) is not None:
                rgb_color = color_util.color_rgbw_to_rgb(*rgbw_color)
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            elif (rgbww_color := params.pop(ATTR_RGBWW_COLOR, None)) is not None:
                # https://github.com/python/mypy/issues/13673
                rgb_color = color_util.color_rgbww_to_rgb(  # type: ignore[call-arg]
                    *rgbww_color,
                    light.min_color_temp_kelvin,
                    light.max_color_temp_kelvin,
                )
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
        elif ATTR_HS_COLOR in params and ColorMode.HS not in supported_color_modes:
            hs_color = params.pop(ATTR_HS_COLOR)
            if ColorMode.RGB in supported_color_modes:
                params[ATTR_RGB_COLOR] = color_util.color_hs_to_RGB(*hs_color)
            elif ColorMode.RGBW in supported_color_modes:
                rgb_color = color_util.color_hs_to_RGB(*hs_color)
                params[ATTR_RGBW_COLOR] = color_util.color_rgb_to_rgbw(*rgb_color)
            elif ColorMode.RGBWW in supported_color_modes:
                rgb_color = color_util.color_hs_to_RGB(*hs_color)
                params[ATTR_RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                    *rgb_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
                )
            elif ColorMode.XY in supported_color_modes:
                params[ATTR_XY_COLOR] = color_util.color_hs_to_xy(*hs_color)
            elif ColorMode.COLOR_TEMP in supported_color_modes:
                xy_color = color_util.color_hs_to_xy(*hs_color)
                params[ATTR_COLOR_TEMP_KELVIN] = color_util.color_xy_to_temperature(
                    *xy_color
                )
                params[_DEPRECATED_ATTR_COLOR_TEMP.value] = (
                    color_util.color_temperature_kelvin_to_mired(
                        params[ATTR_COLOR_TEMP_KELVIN]
                    )
                )
        elif ATTR_RGB_COLOR in params and ColorMode.RGB not in supported_color_modes:
            rgb_color = params.pop(ATTR_RGB_COLOR)
            assert rgb_color is not None
            if TYPE_CHECKING:
                rgb_color = cast(tuple[int, int, int], rgb_color)
            if ColorMode.RGBW in supported_color_modes:
                params[ATTR_RGBW_COLOR] = color_util.color_rgb_to_rgbw(*rgb_color)
            elif ColorMode.RGBWW in supported_color_modes:
                params[ATTR_RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                    *rgb_color,
                    light.min_color_temp_kelvin,
                    light.max_color_temp_kelvin,
                )
            elif ColorMode.HS in supported_color_modes:
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            elif ColorMode.XY in supported_color_modes:
                params[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
            elif ColorMode.COLOR_TEMP in supported_color_modes:
                xy_color = color_util.color_RGB_to_xy(*rgb_color)
                params[ATTR_COLOR_TEMP_KELVIN] = color_util.color_xy_to_temperature(
                    *xy_color
                )
                params[_DEPRECATED_ATTR_COLOR_TEMP.value] = (
                    color_util.color_temperature_kelvin_to_mired(
                        params[ATTR_COLOR_TEMP_KELVIN]
                    )
                )
        elif ATTR_XY_COLOR in params and ColorMode.XY not in supported_color_modes:
            xy_color = params.pop(ATTR_XY_COLOR)
            if ColorMode.HS in supported_color_modes:
                params[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)
            elif ColorMode.RGB in supported_color_modes:
                params[ATTR_RGB_COLOR] = color_util.color_xy_to_RGB(*xy_color)
            elif ColorMode.RGBW in supported_color_modes:
                rgb_color = color_util.color_xy_to_RGB(*xy_color)
                params[ATTR_RGBW_COLOR] = color_util.color_rgb_to_rgbw(*rgb_color)
            elif ColorMode.RGBWW in supported_color_modes:
                rgb_color = color_util.color_xy_to_RGB(*xy_color)
                params[ATTR_RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                    *rgb_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
                )
            elif ColorMode.COLOR_TEMP in supported_color_modes:
                params[ATTR_COLOR_TEMP_KELVIN] = color_util.color_xy_to_temperature(
                    *xy_color
                )
                params[_DEPRECATED_ATTR_COLOR_TEMP.value] = (
                    color_util.color_temperature_kelvin_to_mired(
                        params[ATTR_COLOR_TEMP_KELVIN]
                    )
                )
        elif ATTR_RGBW_COLOR in params and ColorMode.RGBW not in supported_color_modes:
            rgbw_color = params.pop(ATTR_RGBW_COLOR)
            rgb_color = color_util.color_rgbw_to_rgb(*rgbw_color)
            if ColorMode.RGB in supported_color_modes:
                params[ATTR_RGB_COLOR] = rgb_color
            elif ColorMode.RGBWW in supported_color_modes:
                params[ATTR_RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                    *rgb_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
                )
            elif ColorMode.HS in supported_color_modes:
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            elif ColorMode.XY in supported_color_modes:
                params[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
            elif ColorMode.COLOR_TEMP in supported_color_modes:
                xy_color = color_util.color_RGB_to_xy(*rgb_color)
                params[ATTR_COLOR_TEMP_KELVIN] = color_util.color_xy_to_temperature(
                    *xy_color
                )
                params[_DEPRECATED_ATTR_COLOR_TEMP.value] = (
                    color_util.color_temperature_kelvin_to_mired(
                        params[ATTR_COLOR_TEMP_KELVIN]
                    )
                )
        elif (
            ATTR_RGBWW_COLOR in params and ColorMode.RGBWW not in supported_color_modes
        ):
            rgbww_color = params.pop(ATTR_RGBWW_COLOR)
            assert rgbww_color is not None
            if TYPE_CHECKING:
                rgbww_color = cast(tuple[int, int, int, int, int], rgbww_color)
            rgb_color = color_util.color_rgbww_to_rgb(
                *rgbww_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
            )
            if ColorMode.RGB in supported_color_modes:
                params[ATTR_RGB_COLOR] = rgb_color
            elif ColorMode.RGBW in supported_color_modes:
                params[ATTR_RGBW_COLOR] = color_util.color_rgb_to_rgbw(*rgb_color)
            elif ColorMode.HS in supported_color_modes:
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            elif ColorMode.XY in supported_color_modes:
                params[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
            elif ColorMode.COLOR_TEMP in supported_color_modes:
                xy_color = color_util.color_RGB_to_xy(*rgb_color)
                params[ATTR_COLOR_TEMP_KELVIN] = color_util.color_xy_to_temperature(
                    *xy_color
                )
                params[_DEPRECATED_ATTR_COLOR_TEMP.value] = (
                    color_util.color_temperature_kelvin_to_mired(
                        params[ATTR_COLOR_TEMP_KELVIN]
                    )
                )

        # If white is set to True, set it to the light's brightness
        # Add a warning in Home Assistant Core 2024.3 if the brightness is set to an
        # integer.
        if params.get(ATTR_WHITE) is True:
            params[ATTR_WHITE] = light.brightness

        # If both white and brightness are specified, override white
        if (
            supported_color_modes
            and ATTR_WHITE in params
            and ColorMode.WHITE in supported_color_modes
        ):
            params[ATTR_WHITE] = params.pop(ATTR_BRIGHTNESS, params[ATTR_WHITE])

        # Remove deprecated white value if the light supports color mode
        if params.get(ATTR_BRIGHTNESS) == 0 or params.get(ATTR_WHITE) == 0:
            await async_handle_light_off_service(light, call)
        else:
            await light.async_turn_on(**filter_turn_on_params(light, params))

    async def async_handle_light_off_service(
        light: LightEntity, call: ServiceCall
    ) -> None:
        """Handle turning off a light."""
        params = dict(call.data["params"])

        if ATTR_TRANSITION not in params:
            profiles.apply_default(light.entity_id, True, params)

        await light.async_turn_off(**filter_turn_off_params(light, params))

    async def async_handle_toggle_service(
        light: LightEntity, call: ServiceCall
    ) -> None:
        """Handle toggling a light."""
        if light.is_on:
            await async_handle_light_off_service(light, call)
        else:
            await async_handle_light_on_service(light, call)

    # Listen for light on and light off service calls.

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        vol.All(cv.make_entity_service_schema(LIGHT_TURN_ON_SCHEMA), preprocess_data),
        async_handle_light_on_service,
    )

    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        vol.All(cv.make_entity_service_schema(LIGHT_TURN_OFF_SCHEMA), preprocess_data),
        async_handle_light_off_service,
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        vol.All(cv.make_entity_service_schema(LIGHT_TURN_ON_SCHEMA), preprocess_data),
        async_handle_toggle_service,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


def _coerce_none(value: str) -> None:
    """Coerce an empty string as None."""

    if not isinstance(value, str):
        raise vol.Invalid("Expected a string")

    if value:
        raise vol.Invalid("Not an empty string")


@dataclasses.dataclass
class Profile:
    """Representation of a profile.

    The light profiles feature is in a frozen development state
    until otherwise decided in an architecture discussion.
    """

    name: str
    color_x: float | None = dataclasses.field(repr=False)
    color_y: float | None = dataclasses.field(repr=False)
    brightness: int | None
    transition: int | None = None
    hs_color: tuple[float, float] | None = dataclasses.field(init=False)

    SCHEMA = vol.Schema(
        vol.Any(
            vol.ExactSequence(
                (
                    str,
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.byte, _coerce_none),
                )
            ),
            vol.ExactSequence(
                (
                    str,
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.byte, _coerce_none),
                    vol.Any(VALID_TRANSITION, _coerce_none),
                )
            ),
        )
    )

    def __post_init__(self) -> None:
        """Convert xy to hs color."""
        if None in (self.color_x, self.color_y):
            self.hs_color = None
            return

        self.hs_color = color_util.color_xy_to_hs(
            cast(float, self.color_x), cast(float, self.color_y)
        )

    @classmethod
    def from_csv_row(cls, csv_row: list[str]) -> Self:
        """Create profile from a CSV row tuple."""
        return cls(*cls.SCHEMA(csv_row))


class Profiles:
    """Representation of available color profiles.

    The light profiles feature is in a frozen development state
    until otherwise decided in an architecture discussion.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize profiles."""
        self.hass = hass
        self.data: dict[str, Profile] = {}

    def _load_profile_data(self) -> dict[str, Profile]:
        """Load built-in profiles and custom profiles."""
        profile_paths = [
            os.path.join(os.path.dirname(__file__), LIGHT_PROFILES_FILE),
            self.hass.config.path(LIGHT_PROFILES_FILE),
        ]
        profiles = {}

        for profile_path in profile_paths:
            if not os.path.isfile(profile_path):
                continue
            with open(profile_path, encoding="utf8") as inp:
                reader = csv.reader(inp)

                # Skip the header
                next(reader, None)

                try:
                    for rec in reader:
                        profile = Profile.from_csv_row(rec)
                        profiles[profile.name] = profile

                except vol.MultipleInvalid as ex:
                    _LOGGER.error(
                        "Error parsing light profile row '%s' from %s: %s",
                        rec,
                        profile_path,
                        ex,
                    )
                    continue
        return profiles

    async def async_initialize(self) -> None:
        """Load and cache profiles."""
        self.data = await self.hass.async_add_executor_job(self._load_profile_data)

    @callback
    def apply_default(
        self, entity_id: str, state_on: bool | None, params: dict[str, Any]
    ) -> None:
        """Return the default profile for the given light."""
        for _entity_id in (entity_id, "group.all_lights"):
            name = f"{_entity_id}.default"
            if name in self.data:
                if not state_on or not params:
                    self.apply_profile(name, params)
                elif self.data[name].transition is not None:
                    params.setdefault(ATTR_TRANSITION, self.data[name].transition)

    @callback
    def apply_profile(self, name: str, params: dict[str, Any]) -> None:
        """Apply a profile."""
        if (profile := self.data.get(name)) is None:
            return

        color_attributes = (
            ATTR_COLOR_NAME,
            _DEPRECATED_ATTR_COLOR_TEMP.value,
            ATTR_HS_COLOR,
            ATTR_RGB_COLOR,
            ATTR_RGBW_COLOR,
            ATTR_RGBWW_COLOR,
            ATTR_XY_COLOR,
            ATTR_WHITE,
        )

        if profile.hs_color is not None and not any(
            color_attribute in params for color_attribute in color_attributes
        ):
            params[ATTR_HS_COLOR] = profile.hs_color
        if profile.brightness is not None:
            params.setdefault(ATTR_BRIGHTNESS, profile.brightness)
        if profile.transition is not None:
            params.setdefault(ATTR_TRANSITION, profile.transition)


class LightEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes binary sensor entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "brightness",
    "color_mode",
    "hs_color",
    "xy_color",
    "rgb_color",
    "rgbw_color",
    "rgbww_color",
    "color_temp",
    "min_mireds",
    "max_mireds",
    "effect_list",
    "effect",
    "supported_color_modes",
    "supported_features",
}


class LightEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for light entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            ATTR_SUPPORTED_COLOR_MODES,
            ATTR_EFFECT_LIST,
            _DEPRECATED_ATTR_MIN_MIREDS.value,
            _DEPRECATED_ATTR_MAX_MIREDS.value,
            ATTR_MIN_COLOR_TEMP_KELVIN,
            ATTR_MAX_COLOR_TEMP_KELVIN,
            ATTR_BRIGHTNESS,
            ATTR_COLOR_MODE,
            _DEPRECATED_ATTR_COLOR_TEMP.value,
            ATTR_COLOR_TEMP_KELVIN,
            ATTR_EFFECT,
            ATTR_HS_COLOR,
            ATTR_RGB_COLOR,
            ATTR_RGBW_COLOR,
            ATTR_RGBWW_COLOR,
            ATTR_XY_COLOR,
        }
    )

    entity_description: LightEntityDescription
    _attr_brightness: int | None = None
    _attr_color_mode: ColorMode | str | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_effect_list: list[str] | None = None
    _attr_effect: str | None = None
    _attr_hs_color: tuple[float, float] | None = None
    # We cannot set defaults without causing breaking changes until mireds
    # are fully removed. Until then, developers can explicitly
    # use DEFAULT_MIN_KELVIN and DEFAULT_MAX_KELVIN
    _attr_max_color_temp_kelvin: int | None = None
    _attr_min_color_temp_kelvin: int | None = None
    _attr_rgb_color: tuple[int, int, int] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None
    _attr_rgbww_color: tuple[int, int, int, int, int] | None = None
    _attr_supported_color_modes: set[ColorMode] | set[str] | None = None
    _attr_supported_features: LightEntityFeature = LightEntityFeature(0)
    _attr_xy_color: tuple[float, float] | None = None

    # Deprecated, see https://github.com/home-assistant/core/pull/79591
    _attr_color_temp: Final[int | None] = None
    _attr_max_mireds: Final[int] = 500  # = 2000 K
    _attr_min_mireds: Final[int] = 153  # = 6535.94 K (~ 6500 K)

    __color_mode_reported = False

    @cached_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._attr_brightness

    @cached_property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        return self._attr_color_mode

    @property
    def _light_internal_color_mode(self) -> str:
        """Return the color mode of the light with backwards compatibility."""
        if (color_mode := self.color_mode) is None:
            # Backwards compatibility for color_mode added in 2021.4
            # Warning added in 2024.3, break in 2025.3
            if not self.__color_mode_reported and self.__should_report_light_issue():
                self.__color_mode_reported = True
                report_issue = self._suggest_report_issue()
                _LOGGER.warning(
                    (
                        "%s (%s) does not report a color mode, this will stop working "
                        "in Home Assistant Core 2025.3, please %s"
                    ),
                    self.entity_id,
                    type(self),
                    report_issue,
                )

            supported = self._light_internal_supported_color_modes

            if ColorMode.HS in supported and self.hs_color is not None:
                return ColorMode.HS
            if ColorMode.COLOR_TEMP in supported and self.color_temp_kelvin is not None:
                return ColorMode.COLOR_TEMP
            if ColorMode.BRIGHTNESS in supported and self.brightness is not None:
                return ColorMode.BRIGHTNESS
            if ColorMode.ONOFF in supported:
                return ColorMode.ONOFF
            return ColorMode.UNKNOWN

        return color_mode

    @cached_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return self._attr_hs_color

    @cached_property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return self._attr_xy_color

    @cached_property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._attr_rgb_color

    @cached_property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        return self._attr_rgbw_color

    @property
    def _light_internal_rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        return self.rgbw_color

    @cached_property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value [int, int, int, int, int]."""
        return self._attr_rgbww_color

    @final
    @cached_property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds.

        Deprecated, see https://github.com/home-assistant/core/pull/79591
        """
        return self._attr_color_temp

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in Kelvin."""
        if self._attr_color_temp_kelvin is None and (color_temp := self.color_temp):
            report_usage(
                "is using mireds for current light color temperature, when "
                "it should be adjusted to use the kelvin attribute "
                "`_attr_color_temp_kelvin` or override the kelvin property "
                "`color_temp_kelvin` (see "
                "https://github.com/home-assistant/core/pull/79591)",
                breaks_in_ha_version="2026.1",
                core_behavior=ReportBehavior.LOG,
                integration_domain=self.platform.platform_name
                if self.platform
                else None,
                exclude_integrations={DOMAIN},
            )
            return color_util.color_temperature_mired_to_kelvin(color_temp)
        return self._attr_color_temp_kelvin

    @final
    @cached_property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports.

        Deprecated, see https://github.com/home-assistant/core/pull/79591
        """
        return self._attr_min_mireds

    @final
    @cached_property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports.

        Deprecated, see https://github.com/home-assistant/core/pull/79591
        """
        return self._attr_max_mireds

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the warmest color_temp_kelvin that this light supports."""
        if self._attr_min_color_temp_kelvin is None:
            report_usage(
                "is using mireds for warmest light color temperature, when "
                "it should be adjusted to use the kelvin attribute "
                "`_attr_min_color_temp_kelvin` or override the kelvin property "
                "`min_color_temp_kelvin`, possibly with default DEFAULT_MIN_KELVIN "
                "(see https://github.com/home-assistant/core/pull/79591)",
                breaks_in_ha_version="2026.1",
                core_behavior=ReportBehavior.LOG,
                integration_domain=self.platform.platform_name
                if self.platform
                else None,
                exclude_integrations={DOMAIN},
            )
            return color_util.color_temperature_mired_to_kelvin(self.max_mireds)
        return self._attr_min_color_temp_kelvin

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the coldest color_temp_kelvin that this light supports."""
        if self._attr_max_color_temp_kelvin is None:
            report_usage(
                "is using mireds for coldest light color temperature, when "
                "it should be adjusted to use the kelvin attribute "
                "`_attr_max_color_temp_kelvin` or override the kelvin property "
                "`max_color_temp_kelvin`, possibly with default DEFAULT_MAX_KELVIN "
                "(see https://github.com/home-assistant/core/pull/79591)",
                breaks_in_ha_version="2026.1",
                core_behavior=ReportBehavior.LOG,
                integration_domain=self.platform.platform_name
                if self.platform
                else None,
                exclude_integrations={DOMAIN},
            )
            return color_util.color_temperature_mired_to_kelvin(self.min_mireds)
        return self._attr_max_color_temp_kelvin

    @cached_property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._attr_effect_list

    @cached_property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._attr_effect

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features_compat
        supported_color_modes = self._light_internal_supported_color_modes

        if ColorMode.COLOR_TEMP in supported_color_modes:
            min_color_temp_kelvin = self.min_color_temp_kelvin
            max_color_temp_kelvin = self.max_color_temp_kelvin
            data[ATTR_MIN_COLOR_TEMP_KELVIN] = min_color_temp_kelvin
            data[ATTR_MAX_COLOR_TEMP_KELVIN] = max_color_temp_kelvin
            if not max_color_temp_kelvin:
                data[_DEPRECATED_ATTR_MIN_MIREDS.value] = None
            else:
                data[_DEPRECATED_ATTR_MIN_MIREDS.value] = (
                    color_util.color_temperature_kelvin_to_mired(max_color_temp_kelvin)
                )
            if not min_color_temp_kelvin:
                data[_DEPRECATED_ATTR_MAX_MIREDS.value] = None
            else:
                data[_DEPRECATED_ATTR_MAX_MIREDS.value] = (
                    color_util.color_temperature_kelvin_to_mired(min_color_temp_kelvin)
                )
        if LightEntityFeature.EFFECT in supported_features:
            data[ATTR_EFFECT_LIST] = self.effect_list

        data[ATTR_SUPPORTED_COLOR_MODES] = sorted(supported_color_modes)

        return data

    def _light_internal_convert_color(
        self, color_mode: ColorMode | str
    ) -> dict[str, tuple[float, ...]]:
        data: dict[str, tuple[float, ...]] = {}
        if color_mode == ColorMode.HS and (hs_color := self.hs_color):
            data[ATTR_HS_COLOR] = (round(hs_color[0], 3), round(hs_color[1], 3))
            data[ATTR_RGB_COLOR] = color_util.color_hs_to_RGB(*hs_color)
            data[ATTR_XY_COLOR] = color_util.color_hs_to_xy(*hs_color)
        elif color_mode == ColorMode.XY and (xy_color := self.xy_color):
            data[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)
            data[ATTR_RGB_COLOR] = color_util.color_xy_to_RGB(*xy_color)
            data[ATTR_XY_COLOR] = (round(xy_color[0], 6), round(xy_color[1], 6))
        elif color_mode == ColorMode.RGB and (rgb_color := self.rgb_color):
            data[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            data[ATTR_RGB_COLOR] = tuple(int(x) for x in rgb_color[0:3])
            data[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
        elif color_mode == ColorMode.RGBW and (
            rgbw_color := self._light_internal_rgbw_color
        ):
            rgb_color = color_util.color_rgbw_to_rgb(*rgbw_color)
            data[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            data[ATTR_RGB_COLOR] = tuple(int(x) for x in rgb_color[0:3])
            data[ATTR_RGBW_COLOR] = tuple(int(x) for x in rgbw_color[0:4])
            data[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
        elif color_mode == ColorMode.RGBWW and (rgbww_color := self.rgbww_color):
            rgb_color = color_util.color_rgbww_to_rgb(
                *rgbww_color, self.min_color_temp_kelvin, self.max_color_temp_kelvin
            )
            data[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            data[ATTR_RGB_COLOR] = tuple(int(x) for x in rgb_color[0:3])
            data[ATTR_RGBWW_COLOR] = tuple(int(x) for x in rgbww_color[0:5])
            data[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
        elif color_mode == ColorMode.COLOR_TEMP and (
            color_temp_kelvin := self.color_temp_kelvin
        ):
            hs_color = color_util.color_temperature_to_hs(color_temp_kelvin)
            data[ATTR_HS_COLOR] = (round(hs_color[0], 3), round(hs_color[1], 3))
            data[ATTR_RGB_COLOR] = color_util.color_hs_to_RGB(*hs_color)
            data[ATTR_XY_COLOR] = color_util.color_hs_to_xy(*hs_color)
        return data

    def __validate_color_mode(
        self,
        color_mode: ColorMode | str | None,
        supported_color_modes: set[ColorMode] | set[str],
        effect: str | None,
    ) -> None:
        """Validate the color mode."""
        if color_mode is None or color_mode == ColorMode.UNKNOWN:
            # The light is turned off or in an unknown state
            return

        if not effect or effect == EFFECT_OFF:
            # No effect is active, the light must set color mode to one of the supported
            # color modes
            if color_mode in supported_color_modes:
                return
            # Warning added in 2024.3, reject in 2025.3
            if not self.__color_mode_reported and self.__should_report_light_issue():
                self.__color_mode_reported = True
                report_issue = self._suggest_report_issue()
                _LOGGER.warning(
                    (
                        "%s (%s) set to unsupported color mode %s, expected one of %s, "
                        "this will stop working in Home Assistant Core 2025.3, "
                        "please %s"
                    ),
                    self.entity_id,
                    type(self),
                    color_mode,
                    supported_color_modes,
                    report_issue,
                )
            return

        # When an effect is active, the color mode should indicate what adjustments are
        # supported by the effect. To make this possible, we allow the light to set its
        # color mode to on_off, and to brightness if the light allows adjusting
        # brightness, in addition to the otherwise supported color modes.
        effect_color_modes = supported_color_modes | {ColorMode.ONOFF}
        if brightness_supported(effect_color_modes):
            effect_color_modes.add(ColorMode.BRIGHTNESS)

        if color_mode in effect_color_modes:
            return

        # Warning added in 2024.3, reject in 2025.3
        if not self.__color_mode_reported and self.__should_report_light_issue():
            self.__color_mode_reported = True
            report_issue = self._suggest_report_issue()
            _LOGGER.warning(
                (
                    "%s (%s) set to unsupported color mode %s when rendering an effect,"
                    " expected one of %s, this will stop working in Home Assistant "
                    "Core 2025.3, please %s"
                ),
                self.entity_id,
                type(self),
                color_mode,
                effect_color_modes,
                report_issue,
            )
        return

    def __validate_supported_color_modes(
        self,
        supported_color_modes: set[ColorMode] | set[str],
    ) -> None:
        """Validate the supported color modes."""
        if self.__color_mode_reported:
            return

        try:
            valid_supported_color_modes(supported_color_modes)
        except vol.Error:
            # Warning added in 2024.3, reject in 2025.3
            if not self.__color_mode_reported and self.__should_report_light_issue():
                self.__color_mode_reported = True
                report_issue = self._suggest_report_issue()
                _LOGGER.warning(
                    (
                        "%s (%s) sets invalid supported color modes %s, this will stop "
                        "working in Home Assistant Core 2025.3, please %s"
                    ),
                    self.entity_id,
                    type(self),
                    supported_color_modes,
                    report_issue,
                )

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features_compat
        supported_color_modes = self.supported_color_modes
        legacy_supported_color_modes = (
            supported_color_modes or self._light_internal_supported_color_modes
        )
        supported_features_value = supported_features.value
        _is_on = self.is_on
        color_mode = self._light_internal_color_mode if _is_on else None

        effect: str | None
        if LightEntityFeature.EFFECT in supported_features:
            data[ATTR_EFFECT] = effect = self.effect if _is_on else None
        else:
            effect = None

        self.__validate_color_mode(color_mode, legacy_supported_color_modes, effect)

        data[ATTR_COLOR_MODE] = color_mode

        if brightness_supported(supported_color_modes):
            if color_mode in COLOR_MODES_BRIGHTNESS:
                data[ATTR_BRIGHTNESS] = self.brightness
            else:
                data[ATTR_BRIGHTNESS] = None
        elif supported_features_value & _DEPRECATED_SUPPORT_BRIGHTNESS.value:
            # Backwards compatibility for ambiguous / incomplete states
            # Warning is printed by supported_features_compat, remove in 2025.1
            if _is_on:
                data[ATTR_BRIGHTNESS] = self.brightness
            else:
                data[ATTR_BRIGHTNESS] = None

        if color_temp_supported(supported_color_modes):
            if color_mode == ColorMode.COLOR_TEMP:
                color_temp_kelvin = self.color_temp_kelvin
                data[ATTR_COLOR_TEMP_KELVIN] = color_temp_kelvin
                if color_temp_kelvin:
                    data[_DEPRECATED_ATTR_COLOR_TEMP.value] = (
                        color_util.color_temperature_kelvin_to_mired(color_temp_kelvin)
                    )
                else:
                    data[_DEPRECATED_ATTR_COLOR_TEMP.value] = None
            else:
                data[ATTR_COLOR_TEMP_KELVIN] = None
                data[_DEPRECATED_ATTR_COLOR_TEMP.value] = None
        elif supported_features_value & _DEPRECATED_SUPPORT_COLOR_TEMP.value:
            # Backwards compatibility
            # Warning is printed by supported_features_compat, remove in 2025.1
            if _is_on:
                color_temp_kelvin = self.color_temp_kelvin
                data[ATTR_COLOR_TEMP_KELVIN] = color_temp_kelvin
                if color_temp_kelvin:
                    data[_DEPRECATED_ATTR_COLOR_TEMP.value] = (
                        color_util.color_temperature_kelvin_to_mired(color_temp_kelvin)
                    )
                else:
                    data[_DEPRECATED_ATTR_COLOR_TEMP.value] = None
            else:
                data[ATTR_COLOR_TEMP_KELVIN] = None
                data[_DEPRECATED_ATTR_COLOR_TEMP.value] = None

        if color_supported(legacy_supported_color_modes) or color_temp_supported(
            legacy_supported_color_modes
        ):
            data[ATTR_HS_COLOR] = None
            data[ATTR_RGB_COLOR] = None
            data[ATTR_XY_COLOR] = None
            if ColorMode.RGBW in legacy_supported_color_modes:
                data[ATTR_RGBW_COLOR] = None
            if ColorMode.RGBWW in legacy_supported_color_modes:
                data[ATTR_RGBWW_COLOR] = None
            if color_mode:
                data.update(self._light_internal_convert_color(color_mode))

        return data

    @property
    def _light_internal_supported_color_modes(self) -> set[ColorMode] | set[str]:
        """Calculate supported color modes with backwards compatibility."""
        if (_supported_color_modes := self.supported_color_modes) is not None:
            self.__validate_supported_color_modes(_supported_color_modes)
            return _supported_color_modes

        # Backwards compatibility for supported_color_modes added in 2021.4
        # Warning added in 2024.3, remove in 2025.3
        if not self.__color_mode_reported and self.__should_report_light_issue():
            self.__color_mode_reported = True
            report_issue = self._suggest_report_issue()
            _LOGGER.warning(
                (
                    "%s (%s) does not set supported color modes, this will stop working"
                    " in Home Assistant Core 2025.3, please %s"
                ),
                self.entity_id,
                type(self),
                report_issue,
            )
        supported_features = self.supported_features_compat
        supported_features_value = supported_features.value
        supported_color_modes: set[ColorMode] = set()

        if supported_features_value & _DEPRECATED_SUPPORT_COLOR_TEMP.value:
            supported_color_modes.add(ColorMode.COLOR_TEMP)
        if supported_features_value & _DEPRECATED_SUPPORT_COLOR.value:
            supported_color_modes.add(ColorMode.HS)
        if (
            not supported_color_modes
            and supported_features_value & _DEPRECATED_SUPPORT_BRIGHTNESS.value
        ):
            supported_color_modes = {ColorMode.BRIGHTNESS}

        if not supported_color_modes:
            supported_color_modes = {ColorMode.ONOFF}

        return supported_color_modes

    @cached_property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Flag supported color modes."""
        return self._attr_supported_color_modes

    @cached_property
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def supported_features_compat(self) -> LightEntityFeature:
        """Return the supported features as LightEntityFeature.

        Remove this compatibility shim in 2025.1 or later.
        """
        features = self.supported_features
        if type(features) is not int:
            return features
        new_features = LightEntityFeature(features)
        if self._deprecated_supported_features_reported is True:
            return new_features
        self._deprecated_supported_features_reported = True
        report_issue = self._suggest_report_issue()
        report_issue += (
            " and reference "
            "https://developers.home-assistant.io/blog/2023/12/28/support-feature-magic-numbers-deprecation"
        )
        _LOGGER.warning(
            (
                "Entity %s (%s) is using deprecated supported features"
                " values which will be removed in HA Core 2025.1. Instead it should use"
                " %s and color modes, please %s"
            ),
            self.entity_id,
            type(self),
            repr(new_features),
            report_issue,
        )
        return new_features

    def __should_report_light_issue(self) -> bool:
        """Return if light color mode issues should be reported."""
        if not self.platform:
            return True
        # philips_js has known issues, we don't need users to open issues
        return self.platform.platform_name not in {"philips_js"}


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
