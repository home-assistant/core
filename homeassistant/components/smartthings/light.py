"""Support for lights through the SmartThings cloud API."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pysmartthings import Capability

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add lights for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [
            SmartThingsLight(device)
            for device in broker.devices.values()
            if broker.any_assigned(device.device_id, "light")
        ],
        True,
    )


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        Capability.switch,
        Capability.switch_level,
        Capability.color_control,
        Capability.color_temperature,
    ]
    # Must be able to be turned on/off.
    if Capability.switch not in capabilities:
        return None
    # Must have one of these
    light_capabilities = [
        Capability.color_control,
        Capability.color_temperature,
        Capability.switch_level,
    ]
    if any(capability in capabilities for capability in light_capabilities):
        return supported
    return None


def convert_scale(value, value_scale, target_scale, round_digits=4):
    """Convert a value to a different scale."""
    return round(value * target_scale / value_scale, round_digits)


class SmartThingsLight(SmartThingsEntity, LightEntity):
    """Define a SmartThings Light."""

    _attr_supported_color_modes: set[ColorMode]

    # SmartThings does not expose this attribute, instead it's
    # implemented within each device-type handler.  This value is the
    # lowest kelvin found supported across 20+ handlers.
    _attr_max_mireds = 500  # 2000K

    # SmartThings does not expose this attribute, instead it's
    # implemented within each device-type handler.  This value is the
    # highest kelvin found supported across 20+ handlers.
    _attr_min_mireds = 111  # 9000K

    def __init__(self, device):
        """Initialize a SmartThingsLight."""
        super().__init__(device)
        self._attr_supported_color_modes = self._determine_color_modes()
        self._attr_supported_features = self._determine_features()

    def _determine_color_modes(self):
        """Get features supported by the device."""
        color_modes = set()
        # Color Temperature
        if Capability.color_temperature in self._device.capabilities:
            color_modes.add(ColorMode.COLOR_TEMP)
        # Color
        if Capability.color_control in self._device.capabilities:
            color_modes.add(ColorMode.HS)
        # Brightness
        if not color_modes and Capability.switch_level in self._device.capabilities:
            color_modes.add(ColorMode.BRIGHTNESS)
        if not color_modes:
            color_modes.add(ColorMode.ONOFF)

        return color_modes

    def _determine_features(self) -> LightEntityFeature:
        """Get features supported by the device."""
        features = LightEntityFeature(0)
        # Transition
        if Capability.switch_level in self._device.capabilities:
            features |= LightEntityFeature.TRANSITION

        return features

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        tasks = []
        # Color temperature
        if ATTR_COLOR_TEMP in kwargs:
            tasks.append(self.async_set_color_temp(kwargs[ATTR_COLOR_TEMP]))
        # Color
        if ATTR_HS_COLOR in kwargs:
            tasks.append(self.async_set_color(kwargs[ATTR_HS_COLOR]))
        if tasks:
            # Set temp/color first
            await asyncio.gather(*tasks)

        # Switch/brightness/transition
        if ATTR_BRIGHTNESS in kwargs:
            await self.async_set_level(
                kwargs[ATTR_BRIGHTNESS], kwargs.get(ATTR_TRANSITION, 0)
            )
        else:
            await self._device.switch_on(set_status=True)

        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        # Switch/transition
        if ATTR_TRANSITION in kwargs:
            await self.async_set_level(0, int(kwargs[ATTR_TRANSITION]))
        else:
            await self._device.switch_off(set_status=True)

        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update entity attributes when the device status has changed."""
        # Brightness and transition
        if brightness_supported(self._attr_supported_color_modes):
            self._attr_brightness = int(
                convert_scale(self._device.status.level, 100, 255, 0)
            )
        # Color Temperature
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_color_temp = color_util.color_temperature_kelvin_to_mired(
                self._device.status.color_temperature
            )
        # Color
        if ColorMode.HS in self._attr_supported_color_modes:
            self._attr_hs_color = (
                convert_scale(self._device.status.hue, 100, 360),
                self._device.status.saturation,
            )

    async def async_set_color(self, hs_color):
        """Set the color of the device."""
        hue = convert_scale(float(hs_color[0]), 360, 100)
        hue = max(min(hue, 100.0), 0.0)
        saturation = max(min(float(hs_color[1]), 100.0), 0.0)
        await self._device.set_color(hue, saturation, set_status=True)

    async def async_set_color_temp(self, value: float):
        """Set the color temperature of the device."""
        kelvin = color_util.color_temperature_mired_to_kelvin(value)
        kelvin = max(min(kelvin, 30000), 1)
        await self._device.set_color_temperature(kelvin, set_status=True)

    async def async_set_level(self, brightness: int, transition: int):
        """Set the brightness of the light over transition."""
        level = int(convert_scale(brightness, 255, 100, 0))
        # Due to rounding, set level to 1 (one) so we don't inadvertently
        # turn off the light when a low brightness is set.
        level = 1 if level == 0 and brightness > 0 else level
        level = max(min(level, 100), 0)
        duration = int(transition)
        await self._device.set_level(level, duration, set_status=True)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if len(self._attr_supported_color_modes) == 1:
            # The light supports only a single color mode
            return list(self._attr_supported_color_modes)[0]

        # The light supports hs + color temp, determine which one it is
        if self._attr_hs_color and self._attr_hs_color[1]:
            return ColorMode.HS
        return ColorMode.COLOR_TEMP

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.status.switch
