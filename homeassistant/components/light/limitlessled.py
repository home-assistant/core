"""
homeassistant.components.light.limitlessled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for LimitlessLED bulbs, also known as...

- EasyBulb
- AppLight
- AppLamp
- MiLight
- LEDme
- dekolight
- iLight

Configuration:

To use limitlessled you will need to add the following to your
config/configuration.yaml.

light:
  platform: limitlessled
  host: 192.168.1.10
  group_1_name: Living Room
  group_2_name: Bedroom
  group_3_name: Office
  group_4_name: Kitchen

"""
import logging

from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.components.light import (Light, ATTR_BRIGHTNESS,
                                            ATTR_XY_COLOR)
from homeassistant.util.color import color_RGB_to_xy

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['ledcontroller==1.0.7']


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Gets the LimitlessLED lights. """
    import ledcontroller

    led = ledcontroller.LedController(config['host'])

    lights = []
    for i in range(1, 5):
        if 'group_%d_name' % (i) in config:
            lights.append(LimitlessLED(led, i, config['group_%d_name' % (i)]))

    add_devices_callback(lights)


class LimitlessLED(Light):
    """ Represents a LimitlessLED light """

    def __init__(self, led, group, name):
        self.led = led
        self.group = group

        # LimitlessLEDs don't report state, we have track it ourselves.
        self.led.off(self.group)

        self._name = name or DEVICE_DEFAULT_NAME
        self._state = False
        self._brightness = 100
        self._xy_color = color_RGB_to_xy(255, 255, 255)

        # Build a color table that maps an RGB color to a color string
        # recognized by LedController's set_color method
        self._color_table = [(color_RGB_to_xy(*x[0]), x[1]) for x in [
            ((0xFF, 0xFF, 0xFF), 'white'),
            ((0xEE, 0x82, 0xEE), 'violet'),
            ((0x41, 0x69, 0xE1), 'royal_blue'),
            ((0x87, 0xCE, 0xFA), 'baby_blue'),
            ((0x00, 0xFF, 0xFF), 'aqua'),
            ((0x7F, 0xFF, 0xD4), 'royal_mint'),
            ((0x2E, 0x8B, 0x57), 'seafoam_green'),
            ((0x00, 0x80, 0x00), 'green'),
            ((0x32, 0xCD, 0x32), 'lime_green'),
            ((0xFF, 0xFF, 0x00), 'yellow'),
            ((0xDA, 0xA5, 0x20), 'yellow_orange'),
            ((0xFF, 0xA5, 0x00), 'orange'),
            ((0xFF, 0x00, 0x00), 'red'),
            ((0xFF, 0xC0, 0xCB), 'pink'),
            ((0xFF, 0x00, 0xFF), 'fusia'),
            ((0xDA, 0x70, 0xD6), 'lilac'),
            ((0xE6, 0xE6, 0xFA), 'lavendar'),
        ]]

    @property
    def should_poll(self):
        """ No polling needed for a demo light. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def brightness(self):
        return self._brightness

    @property
    def color_xy(self):
        return self._xy_color

    def _xy_to_led_color(self, xy_color):
        """ Convert an XY color to the closest LedController color string """
        def abs_dist_squared(p_0, p_1):
            """ Returns the absolute value of the squared distance """
            return abs((p_0[0] - p_1[0])**2 + (p_0[1] - p_1[1])**2)

        candidates = [(abs_dist_squared(xy_color, x[0]), x[1]) for x in
                      self._color_table]

        # First candidate in the sorted list is closest to desired color:
        return sorted(candidates)[0][1]

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_XY_COLOR in kwargs:
            self._xy_color = kwargs[ATTR_XY_COLOR]

        self.led.set_color(self._xy_to_led_color(self._xy_color), self.group)
        self.led.set_brightness(self._brightness / 255.0, self.group)
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = False
        self.led.off(self.group)
        self.update_ha_state()
