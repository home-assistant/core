"""Support for Lutron Caseta lights."""

from datetime import timedelta
from typing import Any

from pylutron_caseta.color_value import (
    ColorMode as LutronColorMode,
    FullColorValue,
    WarmCoolColorValue,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DEVICE_TYPE_COLOR_TUNE,
    DEVICE_TYPE_SPECTRUM_TUNE,
    DEVICE_TYPE_WHITE_TUNE,
)
from .entity import LutronCasetaUpdatableEntity
from .models import LutronCasetaData

SUPPORTED_COLOR_MODE_DICT = {
    DEVICE_TYPE_SPECTRUM_TUNE: {
        ColorMode.HS,
        ColorMode.COLOR_TEMP,
        ColorMode.WHITE,
    },
    DEVICE_TYPE_WHITE_TUNE: {ColorMode.COLOR_TEMP},
    DEVICE_TYPE_COLOR_TUNE: {
        ColorMode.HS,
        ColorMode.COLOR_TEMP,
        ColorMode.WHITE,
    },
}

WARM_DEVICE_TYPES = {
    DEVICE_TYPE_WHITE_TUNE,
    DEVICE_TYPE_SPECTRUM_TUNE,
    DEVICE_TYPE_COLOR_TUNE,
}


def to_lutron_level(level):
    """Convert the given Home Assistant light level (0-255) to Lutron (0-100)."""
    return int(round((level * 100) / 255))


def to_hass_level(level):
    """Convert the given Lutron (0-100) light level to Home Assistant (0-255)."""
    return int((level * 255) // 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta light platform.

    Adds dimmers from the Caseta bridge associated with the config_entry as
    light entities.
    """
    data = config_entry.runtime_data
    bridge = data.bridge
    light_devices = bridge.get_devices_by_domain(LIGHT_DOMAIN)
    async_add_entities(
        LutronCasetaLight(light_device, data) for light_device in light_devices
    )


class LutronCasetaLight(LutronCasetaUpdatableEntity, LightEntity):
    """Representation of a Lutron Light, including dimmable, white tune, and spectrum tune."""

    _attr_supported_features = LightEntityFeature.TRANSITION
    _prev_brightness: int | None = None

    def __init__(self, light: dict[str, Any], data: LutronCasetaData) -> None:
        """Initialize the light and set the supported color modes."""
        super().__init__(light, data)

        self._attr_min_color_temp_kelvin = self._get_min_color_temp_kelvin(light)
        self._attr_max_color_temp_kelvin = self._get_max_color_temp_kelvin(light)

        light_type = light["type"]
        self._attr_supported_color_modes = SUPPORTED_COLOR_MODE_DICT.get(
            light_type, {ColorMode.BRIGHTNESS}
        )

        self.supports_warm_cool = light_type in WARM_DEVICE_TYPES
        self.supports_warm_dim = light_type in (
            DEVICE_TYPE_SPECTRUM_TUNE,
            DEVICE_TYPE_COLOR_TUNE,
        )
        self.supports_spectrum_tune = light_type in (
            DEVICE_TYPE_SPECTRUM_TUNE,
            DEVICE_TYPE_COLOR_TUNE,
        )

        # Capture the initial brightness so _prev_brightness is correct on startup
        self._sync_prev_brightness_from_device()

    def _get_min_color_temp_kelvin(self, light: dict[str, Any]) -> int:
        """Return minimum supported color temperature."""
        white_tune_range = light.get("white_tuning_range")
        # Default to 1.4k if not found
        if white_tune_range is None or "Min" not in white_tune_range:
            return 1400
        return white_tune_range.get("Min")

    def _get_max_color_temp_kelvin(self, light: dict[str, Any]) -> int:
        """Return maximum supported color temperature."""
        white_tune_range = light.get("white_tuning_range")
        # Default to 10k if not found
        if white_tune_range is None or "Max" not in white_tune_range:
            return 10000
        return white_tune_range.get("Max")

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return to_hass_level(self._device["current_state"])

    def _sync_prev_brightness_from_device(self) -> None:
        """Keep previous brightness in sync with device state."""
        current_level = self._device.get("current_state")
        if current_level is None:
            return

        hass_brightness = to_hass_level(current_level)
        if hass_brightness > 0:
            # Any non-zero brightness (HA or physical) becomes the new last level
            self._prev_brightness = hass_brightness

    async def async_update(self) -> None:
        """Update when forcing a refresh of the device."""
        await super().async_update()
        self._sync_prev_brightness_from_device()

    def _handle_bridge_update(self) -> None:
        """Handle updated data from the bridge."""
        self._sync_prev_brightness_from_device()
        super()._handle_bridge_update()

    async def _async_set_brightness(
        self, brightness: int | None, color_value: LutronColorMode | None, **kwargs: Any
    ) -> None:
        args: dict[str, Any] = {}
        if ATTR_TRANSITION in kwargs:
            args["fade_time"] = timedelta(seconds=kwargs[ATTR_TRANSITION])

        if brightness is not None:
            brightness = to_lutron_level(brightness)

        await self._smartbridge.set_value(
            self.device_id, value=brightness, color_value=color_value, **args
        )

    async def _async_set_warm_dim(self, brightness: int | None, **kwargs: Any) -> None:
        """Set the light to warm dim mode."""
        set_warm_dim_kwargs: dict[str, Any] = {}
        if ATTR_TRANSITION in kwargs:
            set_warm_dim_kwargs["fade_time"] = timedelta(
                seconds=kwargs[ATTR_TRANSITION]
            )

        if brightness is not None:
            brightness = to_lutron_level(brightness)

        await self._smartbridge.set_warm_dim(
            self.device_id, brightness, **set_warm_dim_kwargs
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # first check for "white mode" (WarmDim)
        if (white_color := kwargs.get(ATTR_WHITE)) is not None:
            self._prev_brightness = white_color
            await self._async_set_warm_dim(white_color)
            return

        brightness: int | None

        if ATTR_BRIGHTNESS in kwargs:
            # Explicit brightness: remember it
            brightness = kwargs.pop(ATTR_BRIGHTNESS)
            self._prev_brightness = brightness
        # No explicit brightness: use last known non-zero brightness
        elif self._prev_brightness is None:
            # No history at all: default to full brightness
            brightness = 255
        else:
            brightness = self._prev_brightness

        color: LutronColorMode | None = None
        hs_color: tuple[float, float] | None = kwargs.pop(ATTR_HS_COLOR, None)
        kelvin_color: int | None = kwargs.pop(ATTR_COLOR_TEMP_KELVIN, None)

        if hs_color is not None:
            color = FullColorValue(hs_color[0], hs_color[1])
        elif kelvin_color is not None:
            color = WarmCoolColorValue(kelvin_color)

        await self._async_set_brightness(brightness, color, **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        # Do not touch _prev_brightness here; we want the last non-zero level to survive.
        await self._async_set_brightness(0, None, **kwargs)

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
        current_color: FullColorValue | WarmCoolColorValue | None = self._device.get(
            "color"
        )

        # if bulb is set to full spectrum, return the hue and saturation
        if isinstance(current_color, FullColorValue):
            return (current_color.hue, current_color.saturation)

        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in kelvin."""
        current_color: FullColorValue | WarmCoolColorValue | None = self._device.get(
            "color"
        )

        # if bulb is set to warm cool mode, return the kelvin value
        if isinstance(current_color, WarmCoolColorValue):
            return current_color.kelvin

        return None
