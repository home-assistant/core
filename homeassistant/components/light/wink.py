"""
Support for Wink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.wink/
"""
import colorsys

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR, Light)
from homeassistant.components.wink import WinkDevice
from homeassistant.util import color as color_util
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin

DEPENDENCIES = ['wink']

SUPPORT_WINK = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink lights."""
    import pywink

    add_devices(WinkLight(light) for light in pywink.get_bulbs())


class WinkLight(WinkDevice, Light):
    """Representation of a Wink light."""

    def __init__(self, wink):
        """Initialize the Wink device."""
        WinkDevice.__init__(self, wink)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.wink.state()

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return int(self.wink.brightness() * 255)

    @property
    def rgb_color(self):
        """Current bulb color in RGB."""
        if not self.wink.supports_hue_saturation():
            return None
        else:
            hue = self.wink.color_hue()
            saturation = self.wink.color_saturation()
            value = int(self.wink.brightness() * 255)
            rgb = colorsys.hsv_to_rgb(hue, saturation, value)
            r_value = int(round(rgb[0]))
            g_value = int(round(rgb[1]))
            b_value = int(round(rgb[2]))
            return r_value, g_value, b_value

    @property
    def xy_color(self):
        """Current bulb color in CIE 1931 (XY) color space."""
        if not self.wink.supports_xy_color():
            return None
        return self.wink.color_xy()

    @property
    def color_temp(self):
        """Current bulb color in degrees Kelvin."""
        if not self.wink.supports_temperature():
            return None
        return color_util.color_temperature_kelvin_to_mired(
            self.wink.color_temperature_kelvin())

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_WINK

    # pylint: disable=too-few-public-methods
    def turn_on(self, **kwargs):
        """Turn the switch on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)

        state_kwargs = {
        }

        if rgb_color:
            if self.wink.supports_xy_color():
                xyb = color_util.color_RGB_to_xy(*rgb_color)
                state_kwargs['color_xy'] = xyb[0], xyb[1]
                state_kwargs['brightness'] = xyb[2]
            elif self.wink.supports_hue_saturation():
                hsv = colorsys.rgb_to_hsv(rgb_color[0],
                                          rgb_color[1], rgb_color[2])
                state_kwargs['color_hue_saturation'] = hsv[0], hsv[1]

        if color_temp_mired:
            state_kwargs['color_kelvin'] = mired_to_kelvin(color_temp_mired)

        if brightness:
            state_kwargs['brightness'] = brightness / 255.0

        self.wink.set_state(True, **state_kwargs)

    def turn_off(self):
        """Turn the switch off."""
        self.wink.set_state(False)
