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
from .const import (
    DEVICE_TYPE_SPECTRUM_TUNE,
    DEVICE_TYPE_WHITE_TUNE,
    DOMAIN as CASETA_DOMAIN,
)
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

    _attr_supported_features = LightEntityFeature.TRANSITION

    SUPPORTED_COLOR_MODE_DICT = {
        DEVICE_TYPE_SPECTRUM_TUNE: {
            ColorMode.HS,
            ColorMode.COLOR_TEMP,
            ColorMode.WHITE,
        },
        DEVICE_TYPE_WHITE_TUNE: {ColorMode.COLOR_TEMP},
    }

    def get_min_color_temp_kelvin(self, light) -> int:
        """Return minimum supported color temperature.

        :param light: The light to get the minimum color temperature for.
        """
        white_tune_range = light.get("white_tuning_range")
        # Default to 1.4k if not found
        if white_tune_range is None or "Min" not in white_tune_range:
            return 1400

        return white_tune_range.get("Min")

    def get_max_color_temp_kelvin(self, light) -> int:
        """Return maximum supported color temperature.

        :param light: The light to get the maximum color temperature for.
        """
        white_tune_range = light.get("white_tuning_range")
        # Default to 10k if not found
        if white_tune_range is None or "Max" not in white_tune_range:
            return 10000

        return white_tune_range.get("Max")

    def __init__(self, light, data) -> None:
        """Initialize the light and set the supported color modes.

        :param light: The lutron light device to initialize.
        :param data: The integration data
        """
        super().__init__(light, data)

        self._attr_min_color_temp_kelvin = self.get_min_color_temp_kelvin(light)
        self._attr_max_color_temp_kelvin = self.get_max_color_temp_kelvin(light)

        light_type = light["type"]
        if light_type in self.SUPPORTED_COLOR_MODE_DICT:
            self._attr_supported_color_modes = self.SUPPORTED_COLOR_MODE_DICT[
                light_type
            ]
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        self.supports_warm_cool = light_type in [
            DEVICE_TYPE_WHITE_TUNE,
            DEVICE_TYPE_SPECTRUM_TUNE,
        ]

        self.supports_warm_dim = light_type in [DEVICE_TYPE_SPECTRUM_TUNE]
        self.supports_spectrum_tune = light_type in [DEVICE_TYPE_SPECTRUM_TUNE]

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

        currently_warm_dim = self._device.get("warm_dim", False)
        if self.supports_warm_dim and currently_warm_dim:
            return ColorMode.WHITE

        current_color = self._device.get("color")
        if self.supports_warm_cool and isinstance(current_color, WarmCoolColorValue):
            return ColorMode.COLOR_TEMP

        if self.supports_spectrum_tune and isinstance(current_color, FullColorValue):
            return ColorMode.HS

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
