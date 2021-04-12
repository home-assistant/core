"""Support for lights through the SmartThings cloud API."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pysmartthings import Capability

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    LightEntity,
)
import homeassistant.util.color as color_util

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
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

    def __init__(self, device):
        """Initialize a SmartThingsLight."""
        super().__init__(device)
        self._brightness = None
        self._color_temp = None
        self._hs_color = None
        self._supported_features = self._determine_features()

    def _determine_features(self):
        """Get features supported by the device."""
        features = 0
        # Brightness and transition
        if Capability.switch_level in self._device.capabilities:
            features |= SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
        # Color Temperature
        if Capability.color_temperature in self._device.capabilities:
            features |= SUPPORT_COLOR_TEMP
        # Color
        if Capability.color_control in self._device.capabilities:
            features |= SUPPORT_COLOR

        return features

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        tasks = []
        # Color temperature
        if self._supported_features & SUPPORT_COLOR_TEMP and ATTR_COLOR_TEMP in kwargs:
            tasks.append(self.async_set_color_temp(kwargs[ATTR_COLOR_TEMP]))
        # Color
        if self._supported_features & SUPPORT_COLOR and ATTR_HS_COLOR in kwargs:
            tasks.append(self.async_set_color(kwargs[ATTR_HS_COLOR]))
        if tasks:
            # Set temp/color first
            await asyncio.gather(*tasks)

        # Switch/brightness/transition
        if self._supported_features & SUPPORT_BRIGHTNESS and ATTR_BRIGHTNESS in kwargs:
            await self.async_set_level(
                kwargs[ATTR_BRIGHTNESS], kwargs.get(ATTR_TRANSITION, 0)
            )
        else:
            await self._device.switch_on(set_status=True)

        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        # Switch/transition
        if self._supported_features & SUPPORT_TRANSITION and ATTR_TRANSITION in kwargs:
            await self.async_set_level(0, int(kwargs[ATTR_TRANSITION]))
        else:
            await self._device.switch_off(set_status=True)

        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Update entity attributes when the device status has changed."""
        # Brightness and transition
        if self._supported_features & SUPPORT_BRIGHTNESS:
            self._brightness = int(
                convert_scale(self._device.status.level, 100, 255, 0)
            )
        # Color Temperature
        if self._supported_features & SUPPORT_COLOR_TEMP:
            self._color_temp = color_util.color_temperature_kelvin_to_mired(
                self._device.status.color_temperature
            )
        # Color
        if self._supported_features & SUPPORT_COLOR:
            self._hs_color = (
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
        kelvin = max(min(kelvin, 30000.0), 1.0)
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
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._color_temp

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return self._hs_color

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.status.switch

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        # SmartThings does not expose this attribute, instead it's
        # implemented within each device-type handler.  This value is the
        # lowest kelvin found supported across 20+ handlers.
        return 500  # 2000K

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        # SmartThings does not expose this attribute, instead it's
        # implemented within each device-type handler.  This value is the
        # highest kelvin found supported across 20+ handlers.
        return 111  # 9000K

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features
