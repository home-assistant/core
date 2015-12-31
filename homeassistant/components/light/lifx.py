"""
homeassistant.components.light.lifx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
HA platform implementing LIFX lights.

"""

import logging
import lazylights
import colorsys


from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_COLOR_TEMP)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []
REQUIREMENTS = ['https://github.com/avaidyam/lazylights/archive/'
                'master.zip'
                '#lazylights==3.0.0']

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return LIFX lights. """
    bulbs = lazylights.find_bulbs(timeout=5)
    add_devices_callback([LIFXLight(n) for n in bulbs])

class LIFXLight(Light):
    """ Provides a LIFX bulb. """

    def __init__(self, bulb):
        self._bulb = bulb
        self._info = lazylights.get_state([self._bulb])[0]
        self._name = self._info.label.partition(b'\0')[0].decode('utf-8')

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return int((self._info.brightness / 65535) * 255)

    @property
    def rgb_color(self):
        """ rgb color value. """
        h1, l1, s1 = float(self._info.hue / 65535.0), float(self._info.brightness / 65535.0), float(self._info.saturation / 65535.0)
        r1, g1, b1 = colorsys.hls_to_rgb(float(h1), float(l1), float(s1))
        return [float(r1 * 255.0), float(g1 * 255.0), float(b1 * 255.0)]

    @property
    def color_temp(self):
        """ CT color temperature. """
        return int(1000000 / self._info.kelvin)

    @property
    def is_on(self):
        """ True if device is on. """
        return self._info.power > 0

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        lazylights.set_power([self._bulb], True)

        bright = 1.0
        if ATTR_BRIGHTNESS in kwargs:
            bright = float(kwargs[ATTR_BRIGHTNESS]) / 255.0

        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            r2, g2, b2 = float(rgb[0] / 255.0), float(rgb[1] / 255.0), float(rgb[2] /255.0)
            h2, l2, s2 = colorsys.rgb_to_hls(r2, g2, b2)

            lazylights.set_state([self._bulb], h2 * 360, s2, l2, 2000, 1, False)

        elif "color_temp" in kwargs:
            kelvin = int(1000000 / kwargs[ATTR_COLOR_TEMP])
            lazylights.set_state([self._bulb], 0, 0.0, bright, kelvin, 1, False)
        else:
            lazylights.set_state([self._bulb], 0, 0.0, bright, 3000, 1, False)
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        lazylights.set_power([self._bulb], False)
        self.update_ha_state()

    def update(self):
        self._info = lazylights.get_state([self._bulb])[0]
