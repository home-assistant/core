"""
homeassistant.components.light.limitlessled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for LimitlessLED bulbs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.limitlessled/
"""
import logging

from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.components.light import (Light, ATTR_BRIGHTNESS,
                                            ATTR_RGB_COLOR, ATTR_EFFECT,
                                            EFFECT_COLORLOOP, EFFECT_WHITE)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['ledcontroller==1.1.0']

COLOR_TABLE = {
    'white': [0xFF, 0xFF, 0xFF],
    'violet': [0xEE, 0x82, 0xEE],
    'royal_blue': [0x41, 0x69, 0xE1],
    'baby_blue': [0x87, 0xCE, 0xFA],
    'aqua': [0x00, 0xFF, 0xFF],
    'royal_mint': [0x7F, 0xFF, 0xD4],
    'seafoam_green': [0x2E, 0x8B, 0x57],
    'green': [0x00, 0x80, 0x00],
    'lime_green': [0x32, 0xCD, 0x32],
    'yellow': [0xFF, 0xFF, 0x00],
    'yellow_orange': [0xDA, 0xA5, 0x20],
    'orange': [0xFF, 0xA5, 0x00],
    'red': [0xFF, 0x00, 0x00],
    'pink': [0xFF, 0xC0, 0xCB],
    'fusia': [0xFF, 0x00, 0xFF],
    'lilac': [0xDA, 0x70, 0xD6],
    'lavendar': [0xE6, 0xE6, 0xFA],
}


def _distance_squared(rgb1, rgb2):
    """ Return sum of squared distances of each color part. """
    return sum((val1-val2)**2 for val1, val2 in zip(rgb1, rgb2))


def _rgb_to_led_color(rgb_color):
    """ Convert an RGB color to the closest color string and color. """
    return sorted((_distance_squared(rgb_color, color), name)
                  for name, color in COLOR_TABLE.items())[0][1]


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Gets the LimitlessLED lights. """
    import ledcontroller

    # Handle old configuration format:
    bridges = config.get('bridges', [config])

    for bridge_id, bridge in enumerate(bridges):
        bridge['id'] = bridge_id

    pool = ledcontroller.LedControllerPool([x['host'] for x in bridges])

    lights = []
    for bridge in bridges:
        for i in range(1, 5):
            name_key = 'group_%d_name' % i
            if name_key in bridge:
                group_type = bridge.get('group_%d_type' % i, 'rgbw')
                lights.append(LimitlessLED.factory(pool, bridge['id'], i,
                                                   bridge[name_key],
                                                   group_type))

    add_devices_callback(lights)


class LimitlessLED(Light):
    """ Represents a LimitlessLED light """

    @staticmethod
    def factory(pool, controller_id, group, name, group_type):
        ''' Construct a Limitless LED of the appropriate type '''
        if group_type == 'white':
            return WhiteLimitlessLED(pool, controller_id, group, name)
        elif group_type == 'rgbw':
            return RGBWLimitlessLED(pool, controller_id, group, name)

    # pylint: disable=too-many-arguments
    def __init__(self, pool, controller_id, group, name, group_type):
        self.pool = pool
        self.controller_id = controller_id
        self.group = group

        self.pool.execute(self.controller_id, "set_group_type", self.group,
                          group_type)

        # LimitlessLEDs don't report state, we have track it ourselves.
        self.pool.execute(self.controller_id, "off", self.group)

        self._name = name or DEVICE_DEFAULT_NAME
        self._state = False

    @property
    def should_poll(self):
        """ No polling needed. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = False
        self.pool.execute(self.controller_id, "off", self.group)
        self.update_ha_state()


class RGBWLimitlessLED(LimitlessLED):
    """ Represents a RGBW LimitlessLED light """

    def __init__(self, pool, controller_id, group, name):
        super().__init__(pool, controller_id, group, name, 'rgbw')

        self._brightness = 100
        self._led_color = 'white'

    @property
    def brightness(self):
        return self._brightness

    @property
    def rgb_color(self):
        return COLOR_TABLE[self._led_color]

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_RGB_COLOR in kwargs:
            self._led_color = _rgb_to_led_color(kwargs[ATTR_RGB_COLOR])

        effect = kwargs.get(ATTR_EFFECT)

        if effect == EFFECT_COLORLOOP:
            self.pool.execute(self.controller_id, "disco", self.group)
        elif effect == EFFECT_WHITE:
            self.pool.execute(self.controller_id, "white", self.group)
        else:
            self.pool.execute(self.controller_id, "set_color",
                              self._led_color, self.group)

        # Brightness can be set independently of color
        self.pool.execute(self.controller_id, "set_brightness",
                          self._brightness / 255.0, self.group)

        self.update_ha_state()


class WhiteLimitlessLED(LimitlessLED):
    """ Represents a White LimitlessLED light """

    def __init__(self, pool, controller_id, group, name):
        super().__init__(pool, controller_id, group, name, 'white')

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = True
        self.pool.execute(self.controller_id, "on", self.group)
        self.update_ha_state()
