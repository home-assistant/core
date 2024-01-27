"""Support for Lutron Caseta lights."""
from datetime import timedelta
from typing import Any

from pylutron_caseta.color_value import FullColorValue, WarmCoolColorValue

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDeviceUpdatableEntity
from .const import DOMAIN as CASETA_DOMAIN
from .models import LutronCasetaData


def to_lutron_level(level):
    """Convert the given Home Assistant light level (0-255) to Lutron (0-100)."""
    return int(round((level * 100) / 255))


def to_hass_level(level):
    """Convert the given Lutron (0-100) light level to Home Assistant (0-255)."""
    return int((level * 255) // 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta light platform.

    Adds dimmers from the Caseta bridge associated with the config_entry as
    light entities.
    """
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    light_devices = bridge.get_devices_by_domain(DOMAIN)
    async_add_entities(
        LutronCasetaLight(light_device, data) for light_device in light_devices
    )


class LutronCasetaLight(LutronCasetaDeviceUpdatableEntity, LightEntity):
    """Representation of a Lutron Light, including dimmable, white tune, and spectrum tune."""

    def __init__(self, light, data) -> None:
        """Initialize the light and set the supported color modes."""
        super().__init__(light, data)
        if light["type"] == "SpectrumTune":
            self._attr_supported_color_modes = {
                ColorMode.HS,
                ColorMode.COLOR_TEMP,
                ColorMode.BRIGHTNESS,
                ColorMode.WHITE,
            }
        elif light["type"] == "WhiteTune":
            self._attr_supported_color_modes = {
                ColorMode.COLOR_TEMP,
                ColorMode.BRIGHTNESS,
                ColorMode.WHITE,
            }
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    _attr_supported_features = LightEntityFeature.TRANSITION

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return to_hass_level(self._device["current_state"])

    async def _set_brightness(self, brightness, color_value, **kwargs):
        args = {}
        if ATTR_TRANSITION in kwargs:
            args["fade_time"] = timedelta(seconds=kwargs[ATTR_TRANSITION])

        if brightness is not None:
            brightness = to_lutron_level(brightness)
        await self._smartbridge.set_value(
            self.device_id, value=brightness, color_value=color_value, **args
        )

    async def _set_warm_dim(self, brightness, **kwargs):
        """Set the light to warm dim mode."""
        args = {}
        if ATTR_TRANSITION in kwargs:
            args["fade_time"] = timedelta(seconds=kwargs[ATTR_TRANSITION])

        if brightness is not None:
            brightness = to_lutron_level(brightness)

        await self._smartbridge.set_warm_dim(self.device_id, brightness, **args)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # first check for "white mode" (WarmDim)
        white_color = kwargs.pop(ATTR_WHITE, None)
        if white_color is not None:
            await self._set_warm_dim(white_color)
            return

        brightness = kwargs.pop(ATTR_BRIGHTNESS, None)
        color = None
        hs_color = kwargs.pop(ATTR_HS_COLOR, None)
        kelvin_color = kwargs.pop(ATTR_COLOR_TEMP_KELVIN, None)
        if hs_color is not None:
            color = FullColorValue(hs_color[0], hs_color[1])
        elif kelvin_color is not None:
            color = WarmCoolColorValue(kelvin_color)

        # if user is pressing on button nothing is set, so set brightness to 255
        if color is None and brightness is None:
            brightness = 255

        await self._set_brightness(brightness, color, **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._set_brightness(0, None, **kwargs)

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode of the light."""
        warm_dim = self._device.get("warm_dim", False)
        # check if warm dim is set, if so return white mode
        if warm_dim:
            return ColorMode.WHITE

        # check if color is set, if so return color mode
        current_color = self._device.get("color")
        if isinstance(current_color, WarmCoolColorValue):
            return ColorMode.COLOR_TEMP

        if isinstance(current_color, FullColorValue):
            return ColorMode.HS

        # otherwise return default brightness mode
        return ColorMode.BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device["current_state"] > 0

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the current color of the light."""
        current_color = self._device.get("color")

        # if bulb is set to full spectrum, return the hue and saturation
        if isinstance(current_color, FullColorValue):
            return (current_color.hue, current_color.saturation)

        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in kelvin."""
        current_color = self._device.get("color")

        # if bulb is set to warm cool mode, return the kelvin value
        if isinstance(current_color, WarmCoolColorValue):
            return current_color.kelvin

        return None

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum supported color temperature."""
        white_tune_range = self._device.get("white_tuning_range")
        # Default to 10k if not found
        if white_tune_range is None or "Max" not in white_tune_range:
            return 10000

        return white_tune_range.get("Max")

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum supported color temperature."""
        white_tune_range = self._device.get("white_tuning_range")
        # Default to 1.4k if not found
        if white_tune_range is None or "Min" not in white_tune_range:
            return 1400

        return white_tune_range.get("Min")
