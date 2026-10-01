"""Light platform for Xthings Cloud."""

import colorsys
from typing import Any, override

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
    entities: list[LightEntity] = []
    for device_id, device_data in coordinator.data.items():
        dev_type = device_data.get("type")
        if dev_type == "light":
            entities.append(XthingsCloudLight(coordinator, device_id, device_data))
        elif dev_type == "switch":
            entities.append(XthingsCloudSwitch(coordinator, device_id, device_data))
    async_add_entities(entities)


class XthingsCloudBaseLight(XthingsCloudEntity, LightEntity):
    """Xthings Cloud base light entity."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        return self.device_data["status"].get("on")

    @property
    @override
    def brightness(self) -> int | None:
        """Return brightness (0-255)."""
        level = self.device_data["status"].get("brightness")
        if level is not None:
            return round(level * 255 / 100)
        return None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        raise NotImplementedError

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        raise NotImplementedError


class XthingsCloudLight(XthingsCloudBaseLight):
    """Xthings Cloud native light entity."""

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
        self._native_units = device_data["model"] == "A19-C1"
        if self._native_units:
            self._attr_min_color_temp_kelvin = 2700
            self._attr_supported_color_modes = {ColorMode.HS, ColorMode.COLOR_TEMP}
            return
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
    @override
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
    @override
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color value."""
        status = self.device_data["status"]
        hue = status.get("hue")
        saturation = status.get("saturation")
        if hue is not None and saturation is not None:
            if self._native_units:
                lightness = status.get("lightness")
                if lightness is None:
                    return None
                h, s, _ = colorsys.rgb_to_hsv(
                    *colorsys.hls_to_rgb(hue / 360, lightness / 100, saturation / 100)
                )
                return (h * 360, s * 100)
            return (hue, saturation)
        return None

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        temperature = self.device_data["status"].get("temperature")
        if self._native_units and temperature is not None:
            # Approximate interpolation of the advertised range, not calibration.
            return round(2700 + (max(1, min(100, temperature)) - 1) * 3800 / 99)
        return temperature

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        if self.coordinator.uses_native_mqtt(self._device_id):
            changes = {"pw": 1}
            if ATTR_BRIGHTNESS in kwargs:
                changes["br"] = max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))
            if ATTR_COLOR_TEMP_KELVIN in kwargs:
                changes.update(
                    ct=1,
                    tp=max(
                        1,
                        min(
                            100,
                            round(
                                1 + (kwargs[ATTR_COLOR_TEMP_KELVIN] - 2700) * 99 / 3800
                            ),
                        ),
                    ),
                )
            elif ATTR_HS_COLOR in kwargs:
                hue, saturation = kwargs[ATTR_HS_COLOR]
                h, lightness, saturation = colorsys.rgb_to_hls(
                    *colorsys.hsv_to_rgb(hue / 360, saturation / 100, 1)
                )
                changes.update(
                    ct=0,
                    hu=round(h * 360),
                    sa=round(saturation * 100),
                    li=round(lightness * 100),
                )
            await self.coordinator.async_set_native_state(self._device_id, changes)
            return
        client = self.coordinator.client

        if ATTR_HS_COLOR in kwargs:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            status = self.device_data["status"]
            lightness = status.get("lightness", 50)
            cur_brightness = status.get("brightness", 100)
            if ATTR_BRIGHTNESS in kwargs:
                lightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
                cur_brightness = lightness
            if self._native_units:
                _, lightness, saturation = colorsys.rgb_to_hls(
                    *colorsys.hsv_to_rgb(hue / 360, saturation / 100, 1)
                )
                lightness = round(lightness * 100)
                saturation *= 100
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
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            status = self.device_data["status"]
            cur_brightness = status.get("brightness", 100)
            if ATTR_BRIGHTNESS in kwargs:
                cur_brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await client.async_brite_color(
                self._device_id,
                {
                    "colortype": 1,
                    "temperature": (
                        max(
                            1,
                            min(
                                100,
                                round(
                                    1
                                    + (kwargs[ATTR_COLOR_TEMP_KELVIN] - 2700)
                                    * 99
                                    / 3800
                                ),
                            ),
                        )
                        if self._native_units
                        else kwargs[ATTR_COLOR_TEMP_KELVIN]
                    ),
                    "brightness": cur_brightness,
                },
            )
        elif ATTR_BRIGHTNESS in kwargs:
            brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await client.async_brite_brightness(self._device_id, brightness)
        else:
            await client.async_brite_on(self._device_id)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        if self.coordinator.uses_native_mqtt(self._device_id):
            await self.coordinator.async_set_native_state(self._device_id, {"pw": 0})
            return
        await self.coordinator.client.async_brite_off(self._device_id)


class XthingsCloudSwitch(XthingsCloudBaseLight):
    """Xthings Cloud switch device exposed as a light entity."""

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device_id, device_data)
        status = device_data["status"]
        if "brightness" in status:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {self._attr_color_mode}

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        client = self.coordinator.client
        if ATTR_BRIGHTNESS in kwargs:
            modes = self._attr_supported_color_modes or set()
            if ColorMode.BRIGHTNESS in modes:
                brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
                await client.async_switch_brightness(self._device_id, brightness)
                return
        await client.async_switch_on(self._device_id)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.coordinator.client.async_switch_off(self._device_id)
