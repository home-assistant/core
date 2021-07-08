"""Support for the Elgato Avea lights."""
import avea  # pylint: disable=import-error

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.util.color as color_util

SUPPORT_AVEA = SUPPORT_BRIGHTNESS | SUPPORT_COLOR


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Avea platform."""
    try:
        nearby_bulbs = avea.discover_avea_bulbs()
        for bulb in nearby_bulbs:
            bulb.get_name()
            bulb.get_brightness()
    except OSError as err:
        raise PlatformNotReady from err

    add_entities(AveaLight(bulb) for bulb in nearby_bulbs)


class AveaLight(LightEntity):
    """Representation of an Avea."""

    _attr_supported_features = SUPPORT_AVEA

    def __init__(self, light):
        """Initialize an AveaLight."""
        self._light = light
        self._attr_name = light.name
        self._attr_brightness = light.brightness

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        if not kwargs:
            self._light.set_brightness(4095)
        else:
            if ATTR_BRIGHTNESS in kwargs:
                bright = round((kwargs[ATTR_BRIGHTNESS] / 255) * 4095)
                self._light.set_brightness(bright)
            if ATTR_HS_COLOR in kwargs:
                rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
                self._light.set_rgb(rgb[0], rgb[1], rgb[2])

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.set_brightness(0)

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        brightness = self._light.get_brightness()
        if brightness is not None:
            self._attr_is_on = brightness != 0
            self._attr_brightness = round(255 * (brightness / 4095))
