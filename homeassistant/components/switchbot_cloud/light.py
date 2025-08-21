"""Support for the Switchbot Light."""

import asyncio
from typing import Any

from switchbot_api import (
    CommonCommands,
    Device,
    Remote,
    RGBWLightCommands,
    RGBWWLightCommands,
    SwitchBotAPI,
)

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import AFTER_COMMAND_REFRESH, DOMAIN
from .entity import SwitchBotCloudEntity


def value_map_brightness(value: int) -> int:
    """Return value for brightness map."""
    return int(value / 255 * 100)


def brightness_map_value(value: int) -> int:
    """Return brightness from map value."""
    return int(value * 255 / 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.lights
    )


class SwitchBotCloudLight(SwitchBotCloudEntity, LightEntity):
    """Base Class for SwitchBot Light."""

    _attr_is_on: bool | None = None
    _attr_name: str | None = None

    _attr_color_mode = ColorMode.UNKNOWN

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        power: str | None = self.coordinator.data.get("power")
        brightness: int | None = self.coordinator.data.get("brightness")
        color: str | None = self.coordinator.data.get("color")
        color_temperature: int | None = self.coordinator.data.get("colorTemperature")
        self._attr_is_on = power == "on" if power else None
        self._attr_brightness: int | None = (
            brightness_map_value(brightness) if brightness else None
        )
        self._attr_rgb_color: tuple | None = (
            (tuple(int(i) for i in color.split(":"))) if color else None
        )
        self._attr_color_temp_kelvin: int | None = (
            color_temperature if color_temperature else None
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness: int | None = kwargs.get("brightness")
        rgb_color: tuple[int, int, int] | None = kwargs.get("rgb_color")
        color_temp_kelvin: int | None = kwargs.get("color_temp_kelvin")
        if brightness is not None:
            self._attr_color_mode = ColorMode.RGB
            await self._send_brightness_command(brightness)
        elif rgb_color is not None:
            self._attr_color_mode = ColorMode.RGB
            await self._send_rgb_color_command(rgb_color)
        elif color_temp_kelvin is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            await self._send_color_temperature_command(color_temp_kelvin)
        else:
            self._attr_color_mode = ColorMode.RGB
            await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def _send_brightness_command(self, brightness: int) -> None:
        """Send a brightness command."""
        await self.send_api_command(
            RGBWLightCommands.SET_BRIGHTNESS,
            parameters=str(value_map_brightness(brightness)),
        )

    async def _send_rgb_color_command(self, rgb_color: tuple) -> None:
        """Send an RGB command."""
        await self.send_api_command(
            RGBWLightCommands.SET_COLOR,
            parameters=f"{rgb_color[2]}:{rgb_color[1]}:{rgb_color[0]}",
        )

    async def _send_color_temperature_command(self, color_temp_kelvin: int) -> None:
        """Send a color temperature command."""
        await self.send_api_command(
            RGBWWLightCommands.SET_COLOR_TEMPERATURE,
            parameters=str(color_temp_kelvin),
        )


class SwitchBotCloudStripLight(SwitchBotCloudLight):
    """Representation of a SwitchBot Strip Light."""

    _attr_supported_color_modes = {ColorMode.RGB}


class SwitchBotCloudRGBWWLight(SwitchBotCloudLight):
    """Representation of SwitchBot |Strip Light|Floor Lamp|Color Bulb."""

    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2700

    _attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}

    async def _send_brightness_command(self, brightness: int) -> None:
        """Send a brightness command."""
        await self.send_api_command(
            RGBWWLightCommands.SET_BRIGHTNESS,
            parameters=str(value_map_brightness(brightness)),
        )

    async def _send_rgb_color_command(self, rgb_color: tuple) -> None:
        """Send an RGB command."""
        await self.send_api_command(
            RGBWWLightCommands.SET_COLOR,
            parameters=f"{rgb_color[0]}:{rgb_color[1]}:{rgb_color[2]}",
        )


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudStripLight | SwitchBotCloudRGBWWLight:
    """Make a SwitchBotCloudLight."""
    if device.device_type == "Strip Light":
        return SwitchBotCloudStripLight(api, device, coordinator)
    return SwitchBotCloudRGBWWLight(api, device, coordinator)
