"""Light platform for Homecast."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomecastConfigEntry
from .entity import HomecastEntity

# Mirek <-> Kelvin conversion
MIN_MIREK = 140  # ~7143K (cool white)
MAX_MIREK = 500  # 2000K (warm white)
MIN_KELVIN = round(1_000_000 / MAX_MIREK)  # 2000
MAX_KELVIN = round(1_000_000 / MIN_MIREK)  # 7143


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomecastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Homecast lights."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        HomecastLight(coordinator, device)
        for device in (coordinator.data.devices.values() if coordinator.data else [])
        if device.device_type == "light"
    )


class HomecastLight(HomecastEntity, LightEntity):
    """Represents a Homecast light."""

    _attr_name = None

    @property
    def color_mode(self) -> ColorMode:
        """Return the active color mode."""
        device = self.device
        if device is None:
            return ColorMode.ONOFF
        settable = device.settable
        if "hue" in settable and "saturation" in settable:
            return ColorMode.HS
        if "color_temp" in settable:
            return ColorMode.COLOR_TEMP
        if "brightness" in settable:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes."""
        modes: set[ColorMode] = set()
        device = self.device
        if device is None:
            return {ColorMode.ONOFF}
        settable = device.settable
        if "hue" in settable and "saturation" in settable:
            modes.add(ColorMode.HS)
        if "color_temp" in settable:
            modes.add(ColorMode.COLOR_TEMP)
        if "brightness" in settable and not modes:
            modes.add(ColorMode.BRIGHTNESS)
        if not modes:
            modes.add(ColorMode.ONOFF)
        return modes

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        device = self.device
        if device is None:
            return None
        return device.state.get("on")

    @property
    def brightness(self) -> int | None:
        """Return brightness (HA uses 0-255)."""
        device = self.device
        if device is None:
            return None
        val = device.state.get("brightness")
        if val is not None:
            return round(val * 255 / 100)
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value."""
        device = self.device
        if device is None:
            return None
        hue = device.state.get("hue")
        sat = device.state.get("saturation")
        if hue is not None and sat is not None:
            return (float(hue), float(sat))
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        device = self.device
        if device is None:
            return None
        mirek = device.state.get("color_temp")
        if mirek is not None and mirek > 0:
            return round(1_000_000 / mirek)
        return None

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the minimum color temperature in Kelvin."""
        return MIN_KELVIN

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the maximum color temperature in Kelvin."""
        return MAX_KELVIN

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        payload: dict[str, Any] = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            payload["brightness"] = round(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
        if ATTR_HS_COLOR in kwargs:
            payload["hue"] = round(kwargs[ATTR_HS_COLOR][0])
            payload["saturation"] = round(kwargs[ATTR_HS_COLOR][1])
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            payload["color_temp"] = round(1_000_000 / kwargs[ATTR_COLOR_TEMP_KELVIN])
        await self._async_set_state(payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_set_state({"on": False})
