"""Sandbox proxy for ``light`` entities."""

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxLightEntity(SandboxProxyEntity, LightEntity):
    """Proxy for a ``light`` entity in a sandbox."""

    _features_flag = LightEntityFeature

    @property
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON

    @property
    def brightness(self) -> int | None:
        """Return the cached brightness."""
        value = self._state_cache.get(ATTR_BRIGHTNESS)
        return None if value is None else int(value)

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the cached color mode."""
        value = self._state_cache.get(ATTR_COLOR_MODE)
        if value is None:
            return None
        return ColorMode(value)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the cached hs color."""
        val = self._state_cache.get(ATTR_HS_COLOR)
        return tuple(val) if val else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the cached rgb color."""
        val = self._state_cache.get(ATTR_RGB_COLOR)
        return tuple(val) if val else None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the cached rgbw color."""
        val = self._state_cache.get(ATTR_RGBW_COLOR)
        return tuple(val) if val else None

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the cached rgbww color."""
        val = self._state_cache.get(ATTR_RGBWW_COLOR)
        return tuple(val) if val else None

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the cached xy color."""
        val = self._state_cache.get(ATTR_XY_COLOR)
        return tuple(val) if val else None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the cached color temperature in kelvin."""
        value = self._state_cache.get(ATTR_COLOR_TEMP_KELVIN)
        return None if value is None else int(value)

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the cached or default min color temperature."""
        return int(self.description.capabilities.get(ATTR_MIN_COLOR_TEMP_KELVIN, 2000))

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the cached or default max color temperature."""
        return int(self.description.capabilities.get(ATTR_MAX_COLOR_TEMP_KELVIN, 6500))

    @property
    def effect(self) -> str | None:
        """Return the active effect."""
        return self._state_cache.get(ATTR_EFFECT)

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        effects = self.description.capabilities.get(ATTR_EFFECT_LIST)
        return list(effects) if effects else None

    @property
    def supported_color_modes(self) -> set[ColorMode] | None:
        """Return the cached supported color modes set."""
        modes = self.description.capabilities.get(ATTR_SUPPORTED_COLOR_MODES)
        if not modes:
            return None
        return {ColorMode(m) for m in modes}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on as a ``light.turn_on`` service call."""
        await self._call_service("turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off as a ``light.turn_off`` service call."""
        await self._call_service("turn_off", **kwargs)
