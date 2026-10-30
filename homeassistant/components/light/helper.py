"""Helper functions for the light integration."""

from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING, Any, cast

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import color as color_util

from .const import (
    COLOR_MODES_BRIGHTNESS,
    COLOR_MODES_COLOR,
    DATA_PROFILES,
    ColorMode,
    LightEntityCapabilityAttribute,
    LightEntityFeature,
    LightServiceArgument,
)

if TYPE_CHECKING:
    from . import LightEntity

_LOGGER = logging.getLogger(__name__)


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
    color_modes: Iterable[ColorMode],
) -> set[ColorMode]:
    """Validate the given color modes."""
    color_modes = set(color_modes)
    if (
        not color_modes
        or ColorMode.UNKNOWN in color_modes
        or (ColorMode.BRIGHTNESS in color_modes and len(color_modes) > 1)
        or (ColorMode.ONOFF in color_modes and len(color_modes) > 1)
        or (ColorMode.WHITE in color_modes and not color_supported(color_modes))
    ):
        raise probatio.Error(f"Invalid supported_color_modes {sorted(color_modes)}")
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
        return state.attributes.get(
            LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES
        )

    entity_registry = er.async_get(hass)
    if not (entry := entity_registry.async_get(entity_id)):
        raise HomeAssistantError(f"Unknown entity {entity_id}")
    if not entry.capabilities:
        return None

    return entry.capabilities.get(LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES)


def preprocess_turn_on_alternatives(
    hass: HomeAssistant, params: dict[str, Any]
) -> None:
    """Process extra data for turn light on request.

    Async friendly.
    """
    # Bail out, we process this later.
    if (
        LightServiceArgument.BRIGHTNESS_STEP in params
        or LightServiceArgument.BRIGHTNESS_STEP_PCT in params
    ):
        return

    if LightServiceArgument.PROFILE in params:
        hass.data[DATA_PROFILES].apply_profile(
            params.pop(LightServiceArgument.PROFILE), params
        )

    if (color_name := params.pop(LightServiceArgument.COLOR_NAME, None)) is not None:
        try:
            params[LightServiceArgument.RGB_COLOR] = tuple(
                color_util.color_name_to_rgb(color_name)
            )
        except ValueError:
            _LOGGER.warning("Got unknown color %s, falling back to white", color_name)
            params[LightServiceArgument.RGB_COLOR] = (255, 255, 255)

    brightness_pct = params.pop(LightServiceArgument.BRIGHTNESS_PCT, None)
    if brightness_pct is not None:
        params[LightServiceArgument.BRIGHTNESS] = round(255 * brightness_pct / 100)


def filter_turn_off_params(
    light: LightEntity, params: dict[str, Any]
) -> dict[str, Any]:
    """Filter out params not used in turn off or not supported by the light."""
    if not params:
        return params

    supported_features = light.supported_features

    if LightEntityFeature.FLASH not in supported_features:
        params.pop(LightServiceArgument.FLASH, None)
    if LightEntityFeature.TRANSITION not in supported_features:
        params.pop(LightServiceArgument.TRANSITION, None)

    return {
        k: v
        for k, v in params.items()
        if k in (LightServiceArgument.TRANSITION, LightServiceArgument.FLASH)
    }


def process_turn_off_params(
    hass: HomeAssistant, light: LightEntity, params: dict[str, Any]
) -> dict[str, Any]:
    """Process light turn off params."""
    params = dict(params)

    if LightServiceArgument.TRANSITION not in params:
        hass.data[DATA_PROFILES].apply_default(light.entity_id, True, params)

    return params


def filter_turn_on_params(light: LightEntity, params: dict[str, Any]) -> dict[str, Any]:
    """Filter out params not supported by the light."""
    supported_features = light.supported_features

    if LightEntityFeature.EFFECT not in supported_features:
        params.pop(LightServiceArgument.EFFECT, None)
    if LightEntityFeature.FLASH not in supported_features:
        params.pop(LightServiceArgument.FLASH, None)
    if LightEntityFeature.TRANSITION not in supported_features:
        params.pop(LightServiceArgument.TRANSITION, None)

    supported_color_modes = (
        light._light_internal_supported_color_modes  # noqa: SLF001
    )
    if not brightness_supported(supported_color_modes):
        params.pop(LightServiceArgument.BRIGHTNESS, None)
    if ColorMode.COLOR_TEMP not in supported_color_modes:
        params.pop(LightServiceArgument.COLOR_TEMP_KELVIN, None)
    if ColorMode.HS not in supported_color_modes:
        params.pop(LightServiceArgument.HS_COLOR, None)
    if ColorMode.RGB not in supported_color_modes:
        params.pop(LightServiceArgument.RGB_COLOR, None)
    if ColorMode.RGBW not in supported_color_modes:
        params.pop(LightServiceArgument.RGBW_COLOR, None)
    if ColorMode.RGBWW not in supported_color_modes:
        params.pop(LightServiceArgument.RGBWW_COLOR, None)
    if ColorMode.WHITE not in supported_color_modes:
        params.pop(LightServiceArgument.WHITE, None)
    if ColorMode.XY not in supported_color_modes:
        params.pop(LightServiceArgument.XY_COLOR, None)

    return params


def process_turn_on_params(  # noqa: C901
    hass: HomeAssistant, light: LightEntity, params: dict[str, Any]
) -> dict[str, Any]:
    """Process light turn on params."""
    params = dict(params)

    # Only process params once we processed brightness step
    if params and (
        LightServiceArgument.BRIGHTNESS_STEP in params
        or LightServiceArgument.BRIGHTNESS_STEP_PCT in params
    ):
        brightness = light.brightness if light.is_on and light.brightness else 0

        if LightServiceArgument.BRIGHTNESS_STEP in params:
            brightness += params.pop(LightServiceArgument.BRIGHTNESS_STEP)

        else:
            brightness_pct = round(brightness / 255 * 100)
            brightness = round(
                (brightness_pct + params.pop(LightServiceArgument.BRIGHTNESS_STEP_PCT))
                / 100
                * 255
            )

        params[LightServiceArgument.BRIGHTNESS] = max(0, min(255, brightness))

        preprocess_turn_on_alternatives(hass, params)

    if (not params or not light.is_on) or (
        params and LightServiceArgument.TRANSITION not in params
    ):
        hass.data[DATA_PROFILES].apply_default(light.entity_id, light.is_on, params)

    supported_color_modes = light._light_internal_supported_color_modes  # noqa: SLF001

    # If a color temperature is specified, emulate it if not supported by the light
    if LightServiceArgument.COLOR_TEMP_KELVIN in params:
        if (
            ColorMode.COLOR_TEMP not in supported_color_modes
            and ColorMode.RGBWW in supported_color_modes
        ):
            color_temp = params.pop(LightServiceArgument.COLOR_TEMP_KELVIN)
            brightness = cast(
                int,
                params.get(LightServiceArgument.BRIGHTNESS, light.brightness or 255),
            )
            params[LightServiceArgument.RGBWW_COLOR] = (
                color_util.color_temperature_to_rgbww(
                    color_temp,
                    brightness,
                    light.min_color_temp_kelvin,
                    light.max_color_temp_kelvin,
                )
            )
        elif ColorMode.COLOR_TEMP not in supported_color_modes:
            color_temp = params.pop(LightServiceArgument.COLOR_TEMP_KELVIN)
            if color_supported(supported_color_modes):
                params[LightServiceArgument.HS_COLOR] = (
                    color_util.color_temperature_to_hs(color_temp)
                )

    # If a color is specified, convert to the color space supported by the light
    rgb_color: tuple[int, int, int] | None
    rgbww_color: tuple[int, int, int, int, int] | None
    if (
        LightServiceArgument.HS_COLOR in params
        and ColorMode.HS not in supported_color_modes
    ):
        hs_color = params.pop(LightServiceArgument.HS_COLOR)
        if ColorMode.RGB in supported_color_modes:
            params[LightServiceArgument.RGB_COLOR] = color_util.color_hs_to_RGB(
                *hs_color
            )
        elif ColorMode.RGBW in supported_color_modes:
            rgb_color = color_util.color_hs_to_RGB(*hs_color)
            params[LightServiceArgument.RGBW_COLOR] = color_util.color_rgb_to_rgbw(
                *rgb_color
            )
        elif ColorMode.RGBWW in supported_color_modes:
            rgb_color = color_util.color_hs_to_RGB(*hs_color)
            params[LightServiceArgument.RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                *rgb_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
            )
        elif ColorMode.XY in supported_color_modes:
            params[LightServiceArgument.XY_COLOR] = color_util.color_hs_to_xy(*hs_color)
        elif ColorMode.COLOR_TEMP in supported_color_modes:
            xy_color = color_util.color_hs_to_xy(*hs_color)
            params[LightServiceArgument.COLOR_TEMP_KELVIN] = (
                color_util.color_xy_to_temperature(*xy_color)
            )
    elif (
        LightServiceArgument.RGB_COLOR in params
        and ColorMode.RGB not in supported_color_modes
    ):
        rgb_color = params.pop(LightServiceArgument.RGB_COLOR)
        assert rgb_color is not None
        if TYPE_CHECKING:
            rgb_color = cast(tuple[int, int, int], rgb_color)
        if ColorMode.RGBW in supported_color_modes:
            params[LightServiceArgument.RGBW_COLOR] = color_util.color_rgb_to_rgbw(
                *rgb_color
            )
        elif ColorMode.RGBWW in supported_color_modes:
            params[LightServiceArgument.RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                *rgb_color,
                light.min_color_temp_kelvin,
                light.max_color_temp_kelvin,
            )
        elif ColorMode.HS in supported_color_modes:
            params[LightServiceArgument.HS_COLOR] = color_util.color_RGB_to_hs(
                *rgb_color
            )
        elif ColorMode.XY in supported_color_modes:
            params[LightServiceArgument.XY_COLOR] = color_util.color_RGB_to_xy(
                *rgb_color
            )
        elif ColorMode.COLOR_TEMP in supported_color_modes:
            xy_color = color_util.color_RGB_to_xy(*rgb_color)
            params[LightServiceArgument.COLOR_TEMP_KELVIN] = (
                color_util.color_xy_to_temperature(*xy_color)
            )
    elif (
        LightServiceArgument.XY_COLOR in params
        and ColorMode.XY not in supported_color_modes
    ):
        xy_color = params.pop(LightServiceArgument.XY_COLOR)
        if ColorMode.HS in supported_color_modes:
            params[LightServiceArgument.HS_COLOR] = color_util.color_xy_to_hs(*xy_color)
        elif ColorMode.RGB in supported_color_modes:
            params[LightServiceArgument.RGB_COLOR] = color_util.color_xy_to_RGB(
                *xy_color
            )
        elif ColorMode.RGBW in supported_color_modes:
            rgb_color = color_util.color_xy_to_RGB(*xy_color)
            params[LightServiceArgument.RGBW_COLOR] = color_util.color_rgb_to_rgbw(
                *rgb_color
            )
        elif ColorMode.RGBWW in supported_color_modes:
            rgb_color = color_util.color_xy_to_RGB(*xy_color)
            params[LightServiceArgument.RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                *rgb_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
            )
        elif ColorMode.COLOR_TEMP in supported_color_modes:
            params[LightServiceArgument.COLOR_TEMP_KELVIN] = (
                color_util.color_xy_to_temperature(*xy_color)
            )
    elif (
        LightServiceArgument.RGBW_COLOR in params
        and ColorMode.RGBW not in supported_color_modes
    ):
        rgbw_color = params.pop(LightServiceArgument.RGBW_COLOR)
        rgb_color = color_util.color_rgbw_to_rgb(*rgbw_color)
        if ColorMode.RGB in supported_color_modes:
            params[LightServiceArgument.RGB_COLOR] = rgb_color
        elif ColorMode.RGBWW in supported_color_modes:
            params[LightServiceArgument.RGBWW_COLOR] = color_util.color_rgb_to_rgbww(
                *rgb_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
            )
        elif ColorMode.HS in supported_color_modes:
            params[LightServiceArgument.HS_COLOR] = color_util.color_RGB_to_hs(
                *rgb_color
            )
        elif ColorMode.XY in supported_color_modes:
            params[LightServiceArgument.XY_COLOR] = color_util.color_RGB_to_xy(
                *rgb_color
            )
        elif ColorMode.COLOR_TEMP in supported_color_modes:
            xy_color = color_util.color_RGB_to_xy(*rgb_color)
            params[LightServiceArgument.COLOR_TEMP_KELVIN] = (
                color_util.color_xy_to_temperature(*xy_color)
            )
    elif (
        LightServiceArgument.RGBWW_COLOR in params
        and ColorMode.RGBWW not in supported_color_modes
    ):
        rgbww_color = params.pop(LightServiceArgument.RGBWW_COLOR)
        assert rgbww_color is not None
        if TYPE_CHECKING:
            rgbww_color = cast(tuple[int, int, int, int, int], rgbww_color)
        rgb_color = color_util.color_rgbww_to_rgb(
            *rgbww_color, light.min_color_temp_kelvin, light.max_color_temp_kelvin
        )
        if ColorMode.RGB in supported_color_modes:
            params[LightServiceArgument.RGB_COLOR] = rgb_color
        elif ColorMode.RGBW in supported_color_modes:
            params[LightServiceArgument.RGBW_COLOR] = color_util.color_rgb_to_rgbw(
                *rgb_color
            )
        elif ColorMode.HS in supported_color_modes:
            params[LightServiceArgument.HS_COLOR] = color_util.color_RGB_to_hs(
                *rgb_color
            )
        elif ColorMode.XY in supported_color_modes:
            params[LightServiceArgument.XY_COLOR] = color_util.color_RGB_to_xy(
                *rgb_color
            )
        elif ColorMode.COLOR_TEMP in supported_color_modes:
            xy_color = color_util.color_RGB_to_xy(*rgb_color)
            params[LightServiceArgument.COLOR_TEMP_KELVIN] = (
                color_util.color_xy_to_temperature(*xy_color)
            )

    # If white is set to True, set it to the light's brightness
    # Add a warning in Home Assistant Core 2024.3 if the brightness is set to an
    # integer.
    if params.get(LightServiceArgument.WHITE) is True:
        params[LightServiceArgument.WHITE] = light.brightness

    # If both white and brightness are specified, override white
    if (
        LightServiceArgument.WHITE in params
        and ColorMode.WHITE in supported_color_modes
    ):
        params[LightServiceArgument.WHITE] = params.pop(
            LightServiceArgument.BRIGHTNESS, params[LightServiceArgument.WHITE]
        )

    return params
