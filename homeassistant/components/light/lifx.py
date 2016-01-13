"""
homeassistant.components.light.lifx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
HA platform implementing LIFX lights.

"""

import logging
import colorsys
import time


from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_COLOR_TEMP, ATTR_TRANSITION)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

DEPENDENCIES = []
REQUIREMENTS = ['https://github.com/avaidyam/lazylights/archive/'
                'master.zip'
                '#lazylights==3.0.0']

# First timeout value.
TOUT_START = .2

# Total timeout
TOUT_TOTAL = 5

# Max number of bulbs to find
#Useful for debugging. Set to None for no imposed limit.
MAX_BULBS = None

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    import lazylights
    """ Find and return LIFX lights. """
    bulbs = lazylights.find_bulbs(expected_bulbs=MAX_BULBS, timeout=TOUT_TOTAL)

    add_devices_callback([LIFXLight(n) for n in bulbs][:MAX_BULBS])


class LIFXLight(Light):
    """ Provides a LIFX bulb. """

    def __init__(self, bulb):
        self._bulb = bulb
        self._reachable = True
        self._hue = None
        self._saturation = None
        self._brightness = None
        self._kelvin = None
        self._power = None
        self._level = None
        self._name = None
        self.get_state()
        _LOGGER.info("%s: Created", self._name)

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
        return int((self._brightness / 65535) * 255)

    @property
    def rgb_color(self):
        """ rgb color value. """
        h1, l1, s1 = float(self._hue / 65535.0), float(self._brightness / 65535.0), float(self._saturation / 65535.0)
        r1, g1, b1 = colorsys.hls_to_rgb(float(h1), float(l1), float(s1))
        return [float(r1 * 255.0), float(g1 * 255.0), float(b1 * 255.0)]

    @property
    def color_temp(self):
        """ CT color temperature. """
        return int(1000000 / self._kelvin)

    @property
    def is_on(self):
        """ True if device is reachable and on. """
        return self._reachable and self._power > 0

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        import lazylights
        lazylights.set_power([self._bulb], True)

        bright = 1.0
        fade = 0
        kelvin = 4500

        h = 0
        s = 0

        if ATTR_TRANSITION in kwargs:
           fade = kwargs[ATTR_TRANSITION] * 1000

        if ATTR_BRIGHTNESS in kwargs:
            bright = float(kwargs[ATTR_BRIGHTNESS]) / 255.0

        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            r2, g2, b2 = float(rgb[0] / 255.0), float(rgb[1] / 255.0), float(rgb[2] /255.0)
            h2, l2, s2 = colorsys.rgb_to_hls(r2, g2, b2)

            h = h2 * 360
            s = s2
            bright = l2

        elif "color_temp" in kwargs:
            kelvin = int(1000000 / kwargs[ATTR_COLOR_TEMP])

        _LOGGER.debug("%s: ON", self._name)
        lazylights.set_state([self._bulb], h, s, bright, kelvin, fade, False)

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        import lazylights
        _LOGGER.debug("%s: OFF", self._name)
        lazylights.set_power([self._bulb], False)

    def update(self):
        try:
            self.get_state()
        except:
           _LOGGER.exception("Got exception updating state of %s", self._bulb)

    def get_state(self):
        """ get_state - Get the current light bulb state from the bulb

        LIFx uses UDP as the protocol which is an inherrently lossy protocol.
        LIFX attempts reliability by using acks and sequence numbers much like
        a simple version of TCP, but currently lazylights doesn't impliment this.
        In the interim, we do our own expodential backoff and rerequest attempt
        to get the current light bulb state.

        If after the TOUT_TOTAL we haven't got a valid response then we assume the
        bulb us unreachable and mark it so.
        """
        import lazylights
        _LOGGER.debug("%s: Get state", self._name)
        info = []
        count = 0
        tout = TOUT_START
        ts_start = time.monotonic()
        info = lazylights.get_state([self._bulb], timeout=tout)
        while len(info) == 0:
            if time.monotonic() > ts_start + TOUT_TOTAL:
               self._reachable = False
               _LOGGER.info("%s: Timed out after %s seconds", self._name, TOUT_TOTAL)
               return
            # Do an expodential backoff by doubling the timeout
            tout *= 2
            info = lazylights.get_state([self._bulb], timeout=tout)

        i = info[0]
        self._reachable = True
        self._hue = i.hue
        self._saturation = i.saturation
        self._brightness = i.brightness
        self._kelvin = i.kelvin
        self._power = i.power
        self._name = i.label.partition(b'\0')[0].decode('utf-8')
