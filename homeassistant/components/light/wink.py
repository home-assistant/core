"""
Support for Wink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.wink/
"""
import asyncio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_COLOR, Light)
from homeassistant.components.wink import DOMAIN, WinkDevice
from homeassistant.util import color as color_util
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin

DEPENDENCIES = ['wink']


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
    def hs_color(self):
        """Define current bulb color."""
        if self.wink.supports_xy_color():
            return color_util.color_xy_to_hs(*self.wink.color_xy())

        if self.wink.supports_hue_saturation():
            hue = self.wink.color_hue()
            saturation = self.wink.color_saturation()
            if hue is not None and saturation is not None:
                return hue*360, saturation*100

        return None

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
        supports = SUPPORT_BRIGHTNESS
        if self.wink.supports_temperature():
            supports = supports | SUPPORT_COLOR_TEMP
        if self.wink.supports_xy_color():
            supports = supports | SUPPORT_COLOR
        elif self.wink.supports_hue_saturation():
            supports = supports | SUPPORT_COLOR
        return supports

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)

        state_kwargs = {}

        if hs_color:
            if self.wink.supports_xy_color():
                xy_color = color_util.color_hs_to_xy(*hs_color)
                state_kwargs['color_xy'] = xy_color
            if self.wink.supports_hue_saturation():
                hs_scaled = hs_color[0]/360, hs_color[1]/100
                state_kwargs['color_hue_saturation'] = hs_scaled

        if color_temp_mired:
            state_kwargs['color_kelvin'] = mired_to_kelvin(color_temp_mired)

        if brightness:
            state_kwargs['brightness'] = brightness / 255.0

        self.wink.set_state(True, **state_kwargs)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.wink.set_state(False)
