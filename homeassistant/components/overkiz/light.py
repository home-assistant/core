"""Support for Overkiz lights."""

from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OverkizDataConfigEntry
from .coordinator import OverkizDataUpdateCoordinator
from .entity import OverkizEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz lights from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        OverkizLight(device.device_url, data.coordinator)
        for device in data.platforms[Platform.LIGHT]
    )


class OverkizLight(OverkizEntity, LightEntity):
    """Representation of an Overkiz Light."""

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Initialize a device."""
        super().__init__(device_url, coordinator)

        self._attr_supported_color_modes: set[ColorMode] = set()

        if self.executor.has_command(OverkizCommand.SET_RGB):
            self._attr_color_mode = ColorMode.RGB
        elif self.executor.has_command(OverkizCommand.SET_INTENSITY):
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {self._attr_color_mode}

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return (
            self.executor.select_state(OverkizState.CORE_ON_OFF)
            == OverkizCommandParam.ON
        )

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int] (0-255)."""
        red = self.executor.select_state(OverkizState.CORE_RED_COLOR_INTENSITY)
        green = self.executor.select_state(OverkizState.CORE_GREEN_COLOR_INTENSITY)
        blue = self.executor.select_state(OverkizState.CORE_BLUE_COLOR_INTENSITY)

        if red is None or green is None or blue is None:
            return None

        return (cast(int, red), cast(int, green), cast(int, blue))

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light (0-255)."""
        value = self.executor.select_state(OverkizState.CORE_LIGHT_INTENSITY)
        if value is not None:
            return round(cast(int, value) * 255 / 100)

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if rgb_color is not None:
            await self.executor.async_execute_command(
                OverkizCommand.SET_RGB,
                *[round(float(c)) for c in kwargs[ATTR_RGB_COLOR]],
            )
            return

        if brightness is not None:
            await self.executor.async_execute_command(
                OverkizCommand.SET_INTENSITY, round(float(brightness) / 255 * 100)
            )
            return

        await self.executor.async_execute_command(OverkizCommand.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.executor.async_execute_command(OverkizCommand.OFF)
