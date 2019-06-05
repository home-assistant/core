"""Support for the Elgato Avea lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, Light)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.util.color as color_util


_LOGGER = logging.getLogger(__name__)

SUPPORT_AVEA = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Avea platform."""
    import avea

    nearby_bulbs = avea.discover_avea_bulbs()
    try:
        for bulb in nearby_bulbs:
            bulb.get_name()
            bulb.get_brightness()
    except Exception:
        raise PlatformNotReady

    add_devices(AveaLight(bulb) for bulb in nearby_bulbs)


class AveaLight(Light):
    """Representation of an Avea."""

    def __init__(self, light):
        """Initialize an AveaLight."""
        self._light = light
        self._name = light.name
        self._state = None
        self._brightness = light.brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_AVEA

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
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
            if brightness == 0:
                self._state = False
            else:
                self._state = True
            bright_percent = round((brightness/4095)*100)
            self._brightness = round(255 * (bright_percent / 100))
