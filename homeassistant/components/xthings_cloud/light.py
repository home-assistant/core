"""Light platform for Xthings Cloud."""

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

from .coordinator import XthingsCloudConfigEntry, XthingsCloudCoordinator
from .entity import XthingsCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XthingsCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light platform."""
    coordinator = entry.runtime_data
    entities = [
        XthingsCloudLight(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data["type"] == "light"
    ]
    async_add_entities(entities)


class XthingsCloudLight(XthingsCloudEntity, LightEntity):
    """Xthings Cloud light entity."""

    _attr_min_color_temp_kelvin = 2000
    _attr_max_color_temp_kelvin = 6500

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator, device_id, device_data)
        # Determine supported color modes from device status
        status = device_data["status"]
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
        status = self.device_data["status"]
        color_type = status.get("color_type")
        modes = self._attr_supported_color_modes or set()
        if color_type == 0 and ColorMode.HS in modes:
            return ColorMode.HS
        if color_type == 1 and ColorMode.COLOR_TEMP in modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.HS in modes:
            return ColorMode.HS
        if ColorMode.COLOR_TEMP in modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self.device_data["status"]["on"]

    @property
    def brightness(self) -> int | None:
        """Return brightness (0-255)."""
        level = self.device_data["status"].get("brightness")
        if level is not None:
            return round(level * 255 / 100)
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color value."""
        status = self.device_data["status"]
        hue = status.get("hue")
        saturation = status.get("saturation")
        if hue is not None and saturation is not None:
            return (hue, saturation)
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self.device_data["status"].get("temperature")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        client = self.coordinator.client
        has_color = ATTR_HS_COLOR in kwargs or ATTR_COLOR_TEMP_KELVIN in kwargs
        has_brightness = ATTR_BRIGHTNESS in kwargs
        # Only send on command when no color/brightness adjustment
        if not has_color and not has_brightness:
            await client.async_brite_on(self._device_id)
        # Adjust brightness (standalone, no color change)
        if has_brightness and not has_color:
            brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await client.async_brite_brightness(self._device_id, brightness)
        # Adjust HS color
        if ATTR_HS_COLOR in kwargs:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            status = self.device_data["status"]
            lightness = status.get("lightness", 50)
            cur_brightness = status.get("brightness", 100)
            if ATTR_BRIGHTNESS in kwargs:
                lightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
                cur_brightness = lightness
            await client.async_brite_color(
                self._device_id,
                {
                    "colortype": 0,
                    "hue": round(hue),
                    "saturation": round(saturation),
                    "lightness": lightness,
                    "brightness": cur_brightness,
                },
            )
        # Adjust color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            status = self.device_data["status"]
            cur_brightness = status.get("brightness", 100)
            if ATTR_BRIGHTNESS in kwargs:
                cur_brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await client.async_brite_color(
                self._device_id,
                {
                    "colortype": 1,
                    "temperature": kwargs[ATTR_COLOR_TEMP_KELVIN],
                    "brightness": cur_brightness,
                },
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        await self.coordinator.client.async_brite_off(self._device_id)
