"""BleBox light entities implementation."""
import logging

from blebox_uniapi.error import BadOnValueError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGBW_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGBW,
    LightEntity,
)
from homeassistant.util.color import color_rgb_to_hex, rgb_hex_to_rgb_list

from . import BleBoxEntity, create_blebox_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a BleBox entry."""

    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxLightEntity, "lights"
    )


class BleBoxLightEntity(BleBoxEntity, LightEntity):
    """Representation of BleBox lights."""

    @property
    def supported_color_modes(self):
        """Return supported color modes."""
        return {self.color_mode}

    @property
    def is_on(self):
        """Return if light is on."""
        return self._feature.is_on

    @property
    def brightness(self):
        """Return the name."""
        return self._feature.brightness

    @property
    def color_mode(self):
        """Return the color mode."""
        if self._feature.supports_white and self._feature.supports_color:
            return COLOR_MODE_RGBW
        if self._feature.supports_brightness:
            return COLOR_MODE_BRIGHTNESS
        return COLOR_MODE_ONOFF

    @property
    def rgbw_color(self):
        """Return the hue and saturation."""
        rgbw_hex = self._feature.rgbw_hex
        if rgbw_hex is None:
            return None

        return tuple(rgb_hex_to_rgb_list(rgbw_hex)[0:4])

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""

        rgbw = kwargs.get(ATTR_RGBW_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        feature = self._feature
        value = feature.sensible_on_value

        if brightness is not None:
            value = feature.apply_brightness(value, brightness)

        if rgbw is not None:
            value = feature.apply_white(value, rgbw[3])
            value = feature.apply_color(value, color_rgb_to_hex(*rgbw[0:3]))

        try:
            await self._feature.async_on(value)
        except BadOnValueError as ex:
            _LOGGER.error(
                "Turning on '%s' failed: Bad value %s (%s)", self.name, value, ex
            )

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._feature.async_off()
