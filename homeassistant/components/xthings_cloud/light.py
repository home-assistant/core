"""Light platform for Xthings Cloud."""

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import XthingsCloudCoordinator
from .entity import XthingsCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light platform."""
    coordinator: XthingsCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        XthingsCloudLight(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data.get("type") == "light"
        or (
            device_data.get("type") in ("switch", "plug")
            and "brightness" in device_data.get("status", {})
        )
    ]
    async_add_entities(entities)


class XthingsCloudLight(XthingsCloudEntity, LightEntity):
    """Xthings Cloud light entity."""

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, device_id, device_data)
        self._device_type = device_data.get("type", "light")
        # Determine supported color modes from device status
        status = device_data.get("status", {})
        modes: set[ColorMode] = set()
        if "hue" in status or "saturation" in status:
            modes.add(ColorMode.HS)
        if "temperature" in status:
            modes.add(ColorMode.COLOR_TEMP)
        if not modes and "brightness" in status:
            modes.add(ColorMode.BRIGHTNESS)
        if not modes:
            modes.add(ColorMode.ONOFF)
        self._attr_supported_color_modes = modes

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        status = self.device_data.get("status", {})
        color_type = status.get("color_type")
        if color_type == 0 and ColorMode.HS in self._attr_supported_color_modes:
            return ColorMode.HS
        if color_type == 1 and ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.HS in self._attr_supported_color_modes:
            return ColorMode.HS
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def is_on(self) -> bool | None:
        return self.device_data.get("status", {}).get("on")

    @property
    def brightness(self) -> int | None:
        """Return brightness (0-255)."""
        level = self.device_data.get("status", {}).get("brightness")
        if level is not None:
            return round(level * 255 / 100)
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        status = self.device_data.get("status", {})
        hue = status.get("hue")
        saturation = status.get("saturation")
        if hue is not None and saturation is not None:
            return (hue, saturation)
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        return self.device_data.get("status", {}).get("temperature")

    @property
    def min_color_temp_kelvin(self) -> int:
        return 2000

    @property
    def max_color_temp_kelvin(self) -> int:
        return 6500

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        client = self.coordinator.client
        has_color = ATTR_HS_COLOR in kwargs or ATTR_COLOR_TEMP_KELVIN in kwargs
        has_brightness = ATTR_BRIGHTNESS in kwargs
        # Only send on command when no color/brightness adjustment
        if not has_color and not has_brightness:
            if self._device_type == "plug":
                await client.async_plug_on(self._device_id)
            elif self._device_type == "switch":
                await client.async_switch_on(self._device_id)
            else:
                await client.async_brite_on(self._device_id)
        # Adjust brightness (standalone, no color change)
        if has_brightness and not has_color:
            brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            if self._device_type == "switch":
                await client.async_switch_brightness(self._device_id, brightness)
            else:
                await client.async_brite_brightness(self._device_id, brightness)
        # Adjust HS color
        if ATTR_HS_COLOR in kwargs:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            status = self.device_data.get("status", {})
            lightness = status.get("lightness", 50)
            cur_brightness = status.get("brightness", 100)
            if ATTR_BRIGHTNESS in kwargs:
                lightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
                cur_brightness = lightness
            await client.async_brite_color(self._device_id, {
                "colortype": 0, "hue": round(hue), "saturation": round(saturation),
                "lightness": lightness, "brightness": cur_brightness,
            })
        # Adjust color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            status = self.device_data.get("status", {})
            cur_brightness = status.get("brightness", 100)
            if ATTR_BRIGHTNESS in kwargs:
                cur_brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await client.async_brite_color(self._device_id, {
                "colortype": 1, "temperature": kwargs[ATTR_COLOR_TEMP_KELVIN],
                "brightness": cur_brightness,
            })

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        if self._device_type == "plug":
            await self.coordinator.client.async_plug_off(self._device_id)
        elif self._device_type == "switch":
            await self.coordinator.client.async_switch_off(self._device_id)
        else:
            await self.coordinator.client.async_brite_off(self._device_id)
