"""Support for Magic Home lights."""
from __future__ import annotations

import ast
import logging
from typing import Any, Final

from flux_led.const import MultiColorEffects
from flux_led.protocol import MusicMode
from flux_led.utils import rgbcw_brightness, rgbcw_to_rgbwc, rgbw_brightness
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_EFFECT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .const import (
    CONF_COLORS,
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    CONF_SPEED_PCT,
    CONF_TRANSITION,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
    MIN_CCT_BRIGHTNESS,
    MIN_RGB_BRIGHTNESS,
    MULTI_BRIGHTNESS_COLOR_MODES,
    TRANSITION_GRADUAL,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)
from .coordinator import FluxLedUpdateCoordinator
from .entity import FluxOnOffEntity
from .util import (
    _effect_brightness,
    _flux_color_mode_to_hass,
    _hass_color_modes,
    _min_rgb_brightness,
    _min_rgbw_brightness,
    _min_rgbwc_brightness,
    _str_to_multi_color_effect,
)

_LOGGER = logging.getLogger(__name__)

MODE_ATTRS = {
    ATTR_EFFECT,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
}

ATTR_FOREGROUND_COLOR: Final = "foreground_color"
ATTR_BACKGROUND_COLOR: Final = "background_color"
ATTR_SENSITIVITY: Final = "sensitivity"
ATTR_LIGHT_SCREEN: Final = "light_screen"

# Constant color temp values for 2 flux_led special modes
# Warm-white and Cool-white modes
COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF: Final = 285

EFFECT_CUSTOM: Final = "custom"

SERVICE_CUSTOM_EFFECT: Final = "set_custom_effect"
SERVICE_SET_ZONES: Final = "set_zones"
SERVICE_SET_MUSIC_MODE: Final = "set_music_mode"

CUSTOM_EFFECT_DICT: Final = {
    vol.Required(CONF_COLORS): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=16),
        [vol.All(vol.Coerce(tuple), vol.ExactSequence((cv.byte, cv.byte, cv.byte)))],
    ),
    vol.Optional(CONF_SPEED_PCT, default=50): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(CONF_TRANSITION, default=TRANSITION_GRADUAL): vol.All(
        cv.string, vol.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE])
    ),
}

SET_MUSIC_MODE_DICT: Final = {
    vol.Optional(ATTR_SENSITIVITY, default=100): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(ATTR_BRIGHTNESS, default=100): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(ATTR_EFFECT, default=1): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=16)
    ),
    vol.Optional(ATTR_LIGHT_SCREEN, default=False): bool,
    vol.Optional(ATTR_FOREGROUND_COLOR): vol.All(
        vol.Coerce(tuple), vol.ExactSequence((cv.byte,) * 3)
    ),
    vol.Optional(ATTR_BACKGROUND_COLOR): vol.All(
        vol.Coerce(tuple), vol.ExactSequence((cv.byte,) * 3)
    ),
}

SET_ZONES_DICT: Final = {
    vol.Required(CONF_COLORS): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=2048),
        [vol.All(vol.Coerce(tuple), vol.ExactSequence((cv.byte, cv.byte, cv.byte)))],
    ),
    vol.Optional(CONF_SPEED_PCT, default=50): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(CONF_EFFECT, default=MultiColorEffects.STATIC.name.lower()): vol.All(
        cv.string, vol.In([effect.name.lower() for effect in MultiColorEffects])
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CUSTOM_EFFECT,
        CUSTOM_EFFECT_DICT,
        "async_set_custom_effect",
    )
    platform.async_register_entity_service(
        SERVICE_SET_ZONES,
        SET_ZONES_DICT,
        "async_set_zones",
    )
    platform.async_register_entity_service(
        SERVICE_SET_MUSIC_MODE,
        SET_MUSIC_MODE_DICT,
        "async_set_music_mode",
    )
    options = entry.options

    try:
        custom_effect_colors = ast.literal_eval(
            options.get(CONF_CUSTOM_EFFECT_COLORS) or "[]"
        )
    except (ValueError, TypeError, SyntaxError, MemoryError) as ex:
        _LOGGER.warning(
            "Could not parse custom effect colors for %s: %s", entry.unique_id, ex
        )
        custom_effect_colors = []

    async_add_entities(
        [
            FluxLight(
                coordinator,
                entry.unique_id or entry.entry_id,
                list(custom_effect_colors),
                options.get(CONF_CUSTOM_EFFECT_SPEED_PCT, DEFAULT_EFFECT_SPEED),
                options.get(CONF_CUSTOM_EFFECT_TRANSITION, TRANSITION_GRADUAL),
            )
        ]
    )


class FluxLight(
    FluxOnOffEntity, CoordinatorEntity[FluxLedUpdateCoordinator], LightEntity
):
    """Representation of a Flux light."""

    _attr_name = None

    _attr_supported_features = LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        base_unique_id: str,
        custom_effect_colors: list[tuple[int, int, int]],
        custom_effect_speed_pct: int,
        custom_effect_transition: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, base_unique_id, None)
        self._attr_min_mireds = color_temperature_kelvin_to_mired(self._device.max_temp)
        self._attr_max_mireds = color_temperature_kelvin_to_mired(self._device.min_temp)
        self._attr_supported_color_modes = _hass_color_modes(self._device)
        custom_effects: list[str] = []
        if custom_effect_colors:
            custom_effects.append(EFFECT_CUSTOM)
        self._attr_effect_list = [*self._device.effect_list, *custom_effects]
        self._custom_effect_colors = custom_effect_colors
        self._custom_effect_speed_pct = custom_effect_speed_pct
        self._custom_effect_transition = custom_effect_transition

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._device.brightness

    @property
    def color_temp(self) -> int:
        """Return the kelvin value of this light in mired."""
        return color_temperature_kelvin_to_mired(self._device.color_temp)

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value."""
        return self._device.rgb_unscaled

    @property
    def rgbw_color(self) -> tuple[int, int, int, int]:
        """Return the rgbw color value."""
        return self._device.rgbw

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int]:
        """Return the rgbww aka rgbcw color value."""
        return self._device.rgbcw

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return _flux_color_mode_to_hass(
            self._device.color_mode, self._device.color_modes
        )

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._device.effect

    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        if self._device.requires_turn_on or not kwargs:
            if not self.is_on:
                await self._device.async_turn_on()
            if not kwargs:
                return

        if MODE_ATTRS.intersection(kwargs):
            await self._async_set_mode(**kwargs)
            return
        await self._device.async_set_brightness(self._async_brightness(**kwargs))

    async def _async_set_effect(self, effect: str, brightness: int) -> None:
        """Set an effect."""
        # Custom effect
        if effect == EFFECT_CUSTOM:
            if self._custom_effect_colors:
                await self._device.async_set_custom_pattern(
                    self._custom_effect_colors,
                    self._custom_effect_speed_pct,
                    self._custom_effect_transition,
                )
            return
        await self._device.async_set_effect(
            effect,
            self._device.speed or DEFAULT_EFFECT_SPEED,
            _effect_brightness(brightness),
        )

    @callback
    def _async_brightness(self, **kwargs: Any) -> int:
        """Determine brightness from kwargs or current value."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is None:
            brightness = self.brightness
        # If the brightness was previously 0, the light
        # will not turn on unless brightness is at least 1
        #
        # We previously had a problem with the brightness
        # sometimes reporting as 0 when an effect was in progress,
        # however this has since been resolved in the upstream library
        return max(MIN_RGB_BRIGHTNESS, brightness)

    async def _async_set_mode(self, **kwargs: Any) -> None:
        """Set an effect or color mode."""
        brightness = self._async_brightness(**kwargs)
        # Handle switch to Effect Mode
        if effect := kwargs.get(ATTR_EFFECT):
            await self._async_set_effect(effect, brightness)
            return
        # Handle switch to CCT Color Mode
        if color_temp_mired := kwargs.get(ATTR_COLOR_TEMP):
            color_temp_kelvin = color_temperature_mired_to_kelvin(color_temp_mired)
            if (
                ATTR_BRIGHTNESS not in kwargs
                and self.color_mode in MULTI_BRIGHTNESS_COLOR_MODES
            ):
                # When switching to color temp from RGBWW or RGB&W mode,
                # we do not want the overall brightness of the RGB channels
                brightness = max(MIN_CCT_BRIGHTNESS, *self._device.rgb)
            await self._device.async_set_white_temp(color_temp_kelvin, brightness)
            return
        # Handle switch to RGB Color Mode
        if rgb := kwargs.get(ATTR_RGB_COLOR):
            if not self._device.requires_turn_on:
                rgb = _min_rgb_brightness(rgb)
            red, green, blue = rgb
            await self._device.async_set_levels(red, green, blue, brightness=brightness)
            return
        # Handle switch to RGBW Color Mode
        if rgbw := kwargs.get(ATTR_RGBW_COLOR):
            if ATTR_BRIGHTNESS in kwargs:
                rgbw = rgbw_brightness(rgbw, brightness)
            rgbw = _min_rgbw_brightness(rgbw, self._device.rgbw)
            await self._device.async_set_levels(*rgbw)
            return
        # Handle switch to RGBWW Color Mode
        if rgbcw := kwargs.get(ATTR_RGBWW_COLOR):
            if ATTR_BRIGHTNESS in kwargs:
                rgbcw = rgbcw_brightness(kwargs[ATTR_RGBWW_COLOR], brightness)
            rgbwc = rgbcw_to_rgbwc(rgbcw)
            rgbwc = _min_rgbwc_brightness(rgbwc, self._device.rgbww)
            await self._device.async_set_levels(*rgbwc)
            return
        if (white := kwargs.get(ATTR_WHITE)) is not None:
            await self._device.async_set_levels(w=white)
            return

    async def async_set_custom_effect(
        self, colors: list[tuple[int, int, int]], speed_pct: int, transition: str
    ) -> None:
        """Set a custom effect on the bulb."""
        await self._device.async_set_custom_pattern(
            colors,
            speed_pct,
            transition,
        )

    async def async_set_zones(
        self, colors: list[tuple[int, int, int]], speed_pct: int, effect: str
    ) -> None:
        """Set a colors for zones."""
        await self._device.async_set_zones(
            colors,
            speed_pct,
            _str_to_multi_color_effect(effect),
        )

    async def async_set_music_mode(
        self,
        sensitivity: int,
        brightness: int,
        effect: int,
        light_screen: bool,
        foreground_color: tuple[int, int, int] | None = None,
        background_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Configure music mode."""
        await self._async_ensure_device_on()
        await self._device.async_set_music_mode(
            sensitivity=sensitivity,
            brightness=brightness,
            mode=MusicMode.LIGHT_SCREEN.value if light_screen else None,
            effect=effect,
            foreground_color=foreground_color,
            background_color=background_color,
        )
