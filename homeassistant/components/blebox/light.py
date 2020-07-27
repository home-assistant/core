"""BleBox light entities implementation."""
import logging

from blebox_uniapi.error import BadOnValueError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_rgb_to_hex,
    color_RGB_to_hs,
    rgb_hex_to_rgb_list,
)

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
    def supported_features(self):
        """Return supported features."""
        white = SUPPORT_WHITE_VALUE if self._feature.supports_white else 0
        color = SUPPORT_COLOR if self._feature.supports_color else 0
        brightness = SUPPORT_BRIGHTNESS if self._feature.supports_brightness else 0
        return white | color | brightness

    @property
    def is_on(self):
        """Return if light is on."""
        return self._feature.is_on

    @property
    def brightness(self):
        """Return the name."""
        return self._feature.brightness

    @property
    def white_value(self):
        """Return the white value."""
        return self._feature.white_value

    @property
    def hs_color(self):
        """Return the hue and saturation."""
        rgbw_hex = self._feature.rgbw_hex
        if rgbw_hex is None:
            return None

        rgb = rgb_hex_to_rgb_list(rgbw_hex)[0:3]
        return color_RGB_to_hs(*rgb)

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""

        white = kwargs.get(ATTR_WHITE_VALUE)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        feature = self._feature
        value = feature.sensible_on_value

        if brightness is not None:
            value = feature.apply_brightness(value, brightness)

        if white is not None:
            value = feature.apply_white(value, white)

        if hs_color is not None:
            raw_rgb = color_rgb_to_hex(*color_hs_to_RGB(*hs_color))
            value = feature.apply_color(value, raw_rgb)

        try:
            await self._feature.async_on(value)
        except BadOnValueError as ex:
            _LOGGER.error(
                "Turning on '%s' failed: Bad value %s (%s)", self.name, value, ex
            )

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._feature.async_off()
