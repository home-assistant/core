"""Support for Fibaro lights."""
from __future__ import annotations

import asyncio
from functools import partial

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    ENTITY_ID_FORMAT,
    LightEntity,
    brightness_supported,
    color_supported,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN


def scaleto255(value):
    """Scale the input value from 0-100 to 0-255."""
    # Fibaro has a funny way of storing brightness either 0-100 or 0-99
    # depending on device type (e.g. dimmer vs led)
    if value > 98:
        value = 100
    return max(0, min(255, ((value * 255.0) / 100.0)))


def scaleto100(value):
    """Scale the input value from 0-255 to 0-100."""
    # Make sure a low but non-zero value is not rounded down to zero
    if 0 < value < 3:
        return 1
    return max(0, min(100, ((value * 100.0) / 255.0)))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Fibaro controller devices."""
    async_add_entities(
        [
            FibaroLight(device)
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES]["light"]
        ],
        True,
    )


class FibaroLight(FibaroDevice, LightEntity):
    """Representation of a Fibaro Light, including dimmable."""

    def __init__(self, fibaro_device):
        """Initialize the light."""
        self._brightness = None
        self._last_brightness = 0
        self._update_lock = asyncio.Lock()
        self._attr_supported_color_modes = {}

        self._reset_color = False
        supports_color = (
            "color" in fibaro_device.properties
            or "colorComponents" in fibaro_device.properties
            or "RGB" in fibaro_device.type
            or "rgb" in fibaro_device.type
            or "color" in fibaro_device.baseType
        ) and (
            "setColor" in fibaro_device.actions
            or "setColorComponents" in fibaro_device.actions
        )
        supports_white_v = (
            "setW" in fibaro_device.actions
            or "RGBW" in fibaro_device.type
            or "rgbw" in fibaro_device.type
        )
        supports_dimming = (
            "levelChange" in fibaro_device.interfaces
            or supports_color
            or supports_white_v
        )

        if supports_color:
            if supports_white_v:
                self._attr_supported_color_modes = {COLOR_MODE_RGBW}
                self._attr_color_mode = COLOR_MODE_RGBW
            else:
                self._attr_supported_color_modes = {COLOR_MODE_RGB}
                self._attr_color_mode = COLOR_MODE_RGBW
        if not self._attr_supported_color_modes and supports_dimming:
            self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes = {COLOR_MODE_ONOFF}
            self._attr_color_mode = COLOR_MODE_ONOFF

        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return scaleto255(self._brightness)

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        async with self._update_lock:
            await self.hass.async_add_executor_job(partial(self._turn_on, **kwargs))

    def _turn_on(self, **kwargs):
        """Really turn the light on."""
        if brightness_supported(self.supported_color_modes):
            target_brightness = kwargs.get(ATTR_BRIGHTNESS)

            # No brightness specified, so we either restore it to
            # last brightness or switch it on at maximum level
            if target_brightness is None:
                if self._brightness == 0:
                    if self._last_brightness:
                        self._brightness = self._last_brightness
                    else:
                        self._brightness = 100
            else:
                # We set it to the target brightness and turn it on
                self._brightness = scaleto100(target_brightness)

        if ATTR_RGB_COLOR in kwargs:
            # Update based on parameters
            self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]
            self.call_set_color(*self._attr_rgb_color, 0)

            if self.state == "off":
                self.set_level(min(int(self._brightness), 99))
            return

        if ATTR_RGBW_COLOR in kwargs:
            # Update based on parameters
            self._attr_rgbw_color = kwargs[ATTR_RGBW_COLOR]
            self.call_set_color(*self._attr_rgbw_color)

            if self.state == "off":
                self.set_level(min(int(self._brightness), 99))
            return

        if self._reset_color:
            bri255 = scaleto255(self._brightness)
            self.call_set_color(bri255, bri255, bri255, bri255)

        if brightness_supported(self.supported_color_modes):
            self.set_level(min(int(self._brightness), 99))
            return

        # The simplest case is left for last. No dimming, just switch on
        self.call_turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        async with self._update_lock:
            await self.hass.async_add_executor_job(partial(self._turn_off, **kwargs))

    def _turn_off(self, **kwargs):
        """Really turn the light off."""
        # Let's save the last brightness level before we switch it off
        if (
            (brightness_supported(self.supported_color_modes))
            and self._brightness
            and self._brightness > 0
        ):
            self._last_brightness = self._brightness
        self._brightness = 0
        self.call_turn_off()

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on.

        Dimmable and RGB lights can be on based on different
        properties, so we need to check here several values.
        """
        props = self.fibaro_device.properties
        if self.current_binary_state:
            return True
        if "brightness" in props and props.brightness != "0":
            return True
        if "currentProgram" in props and props.currentProgram != "0":
            return True
        if "currentProgramID" in props and props.currentProgramID != "0":
            return True

        return False

    async def async_update(self):
        """Update the state."""
        async with self._update_lock:
            await self.hass.async_add_executor_job(self._update)

    def _update(self):
        """Really update the state."""
        # Brightness handling
        if brightness_supported(self.supported_color_modes):
            self._brightness = float(self.fibaro_device.properties.value)
            # Fibaro might report 0-99 or 0-100 for brightness,
            # based on device type, so we round up here
            if self._brightness > 99:
                self._brightness = 100
        # Color handling
        if (
            color_supported(self.supported_color_modes)
            and "color" in self.fibaro_device.properties
            and "," in self.fibaro_device.properties.color
        ):
            # Fibaro communicates the color as an 'R, G, B, W' string
            rgbw_s = self.fibaro_device.properties.color
            if rgbw_s == "0,0,0,0" and "lastColorSet" in self.fibaro_device.properties:
                rgbw_s = self.fibaro_device.properties.lastColorSet
            rgbw_list = [int(i) for i in rgbw_s.split(",")][:4]
            self._attr_rgb_color = tuple(rgbw_list[0:3])
            self._attr_rgbw_color = tuple(rgbw_list[0:3])
