"""Sandbox proxy for light entities."""

from __future__ import annotations

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

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxLightEntity(SandboxProxyEntity, LightEntity):
    """Proxy for a light entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy light entity."""
        super().__init__(description, manager)
        self._attr_supported_features = LightEntityFeature(
            description.supported_features
        )

    @property
    def is_on(self) -> bool | None:
        """Return if the light is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def brightness(self) -> int | None:
        """Return the brightness."""
        return self._state_cache.get(ATTR_BRIGHTNESS)

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode."""
        return self._state_cache.get(ATTR_COLOR_MODE)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color."""
        val = self._state_cache.get(ATTR_HS_COLOR)
        return tuple(val) if val else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color."""
        val = self._state_cache.get(ATTR_RGB_COLOR)
        return tuple(val) if val else None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the RGBW color."""
        val = self._state_cache.get(ATTR_RGBW_COLOR)
        return tuple(val) if val else None

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the RGBWW color."""
        val = self._state_cache.get(ATTR_RGBWW_COLOR)
        return tuple(val) if val else None

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the XY color."""
        val = self._state_cache.get(ATTR_XY_COLOR)
        return tuple(val) if val else None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        return self._state_cache.get(ATTR_COLOR_TEMP_KELVIN)

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the min color temperature."""
        return self._description.capabilities.get(
            ATTR_MIN_COLOR_TEMP_KELVIN, 2000
        )

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the max color temperature."""
        return self._description.capabilities.get(
            ATTR_MAX_COLOR_TEMP_KELVIN, 6500
        )

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._state_cache.get(ATTR_EFFECT)

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._description.capabilities.get(ATTR_EFFECT_LIST)

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Return the supported color modes."""
        modes = self._description.capabilities.get(ATTR_SUPPORTED_COLOR_MODES)
        if modes is None:
            return None
        return {ColorMode(m) for m in modes}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)
