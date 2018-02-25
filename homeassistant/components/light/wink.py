"""
Support for Wink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.wink/
"""
import asyncio
import colorsys

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR, Light)
from homeassistant.components.wink import DOMAIN, WinkDevice
from homeassistant.util import color as color_util
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin

DEPENDENCIES = ['wink']

SUPPORT_WINK = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Wink lights."""
    import pywink

    for light in pywink.get_light_bulbs():
        _id = light.object_id() + light.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkLight(light, hass)])
    for light in pywink.get_light_groups():
        _id = light.object_id() + light.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkLight(light, hass)])


class WinkLight(WinkDevice, Light):
    """Representation of a Wink light."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['light'].append(self)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.wink.state()

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self.wink.brightness() is not None:
            return int(self.wink.brightness() * 255)
        return None

    @property
    def rgb_color(self):
        """Define current bulb color in RGB."""
        if not self.wink.supports_hue_saturation():
            return None
        else:
            hue = self.wink.color_hue()
            saturation = self.wink.color_saturation()
            value = int(self.wink.brightness() * 255)
            if hue is None or saturation is None or value is None:
                return None
            rgb = colorsys.hsv_to_rgb(hue, saturation, value)
            r_value = int(round(rgb[0]))
            g_value = int(round(rgb[1]))
            b_value = int(round(rgb[2]))
            return r_value, g_value, b_value

    @property
    def xy_color(self):
        """Define current bulb color in CIE 1931 (XY) color space."""
        if not self.wink.supports_xy_color():
            return None
        return self.wink.color_xy()

    @property
    def color_temp(self):
        """Define current bulb color in degrees Kelvin."""
        if not self.wink.supports_temperature():
            return None
        return color_util.color_temperature_kelvin_to_mired(
            self.wink.color_temperature_kelvin())

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_WINK

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
            if self.wink.supports_hue_saturation():
                hsv = colorsys.rgb_to_hsv(
                    rgb_color[0], rgb_color[1], rgb_color[2])
                state_kwargs['color_hue_saturation'] = hsv[0], hsv[1]

        if color_temp_mired:
            state_kwargs['color_kelvin'] = mired_to_kelvin(color_temp_mired)

        if brightness:
            state_kwargs['brightness'] = brightness / 255.0

        self.wink.set_state(True, **state_kwargs)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.wink.set_state(False)
