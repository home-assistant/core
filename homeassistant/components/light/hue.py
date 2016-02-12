"""
homeassistant.components.light.hue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Hue lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.hue/
"""
import logging
import random
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_XY_COLOR, ATTR_COLOR_TEMP,
    ATTR_TRANSITION, ATTR_FLASH, FLASH_LONG, FLASH_SHORT,
    ATTR_EFFECT, EFFECT_COLORLOOP, EFFECT_RANDOM, ATTR_RGB_COLOR)
from homeassistant.const import (
    DEVICE_DEFAULT_NAME)
from homeassistant.components.hue import (
    HUEBRIDGE, ATTR_HUE_BRIDGEID, ATTR_HUE_LIGHTS)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and add Hue lights. """
    if discovery_info is None:
        return

    # FIXME / debuglog
    _LOGGER.warning('Discovery info: %s', discovery_info)
    bridge_id = discovery_info.get(ATTR_HUE_BRIDGEID)
    for light_id in discovery_info.get(ATTR_HUE_LIGHTS):
        # FIXME / debuglog
        _LOGGER.warning('Found HueLamp: %s', light_id)
        # FIXME / Rewrite this to one add_devices call
        add_devices([HueLight(bridge_id, light_id)])


class HueLight(Light):
    """ Represents a Hue light """

    # pylint: disable=too-many-arguments
    def __init__(self, bridge_id, light_id):
        self.bridge = HUEBRIDGE.get(bridge_id)
        self.light_id = light_id
        # FIXME / debuglog
        _LOGGER.warning('init new light %s on hub %s', light_id, bridge_id)

    def info(self):
        return self.bridge.get_state(ATTR_HUE_LIGHTS, self.light_id)

    @property
    def unique_id(self):
        """ Returns the id of this Hue light """
        return "{}.{}".format(
            self.__class__, self.info().get('uniqueid', self.name))

    @property
    def name(self):
        """ Get the mame of the Hue light. """
        return self.info().get('name', DEVICE_DEFAULT_NAME)

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self.info()['state'].get('bri')

    @property
    def xy_color(self):
        """ XY color value. """
        return self.info()['state'].get('xy')

    @property
    def color_temp(self):
        """ CT color value. """
        return self.info()['state'].get('ct')

    @property
    def is_on(self):
        """ True if device is on. """
        return self.info()['state']['reachable'] and self.info()['state']['on']

    def turn_on(self, **kwargs):
        """ Turn the specified or all lights on. """
        command = {'on': True}

        if ATTR_TRANSITION in kwargs:
            command['transitiontime'] = kwargs[ATTR_TRANSITION] * 10

        if ATTR_BRIGHTNESS in kwargs:
            command['bri'] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_XY_COLOR in kwargs:
            command['xy'] = kwargs[ATTR_XY_COLOR]
        elif ATTR_RGB_COLOR in kwargs:
            command['xy'] = color_util.color_RGB_to_xy(
                *(int(val) for val in kwargs[ATTR_RGB_COLOR]))

        if ATTR_COLOR_TEMP in kwargs:
            command['ct'] = kwargs[ATTR_COLOR_TEMP]

        flash = kwargs.get(ATTR_FLASH)

        if flash == FLASH_LONG:
            command['alert'] = 'lselect'
        elif flash == FLASH_SHORT:
            command['alert'] = 'select'
        elif self.bridge.bridge_type == 'hue':
            command['alert'] = 'none'

        effect = kwargs.get(ATTR_EFFECT)

        if effect == EFFECT_COLORLOOP:
            command['effect'] = 'colorloop'
        elif effect == EFFECT_RANDOM:
            command['hue'] = random.randrange(0, 65535)
            command['sat'] = random.randrange(150, 254)
        elif self.bridge.bridge_type == 'hue':
            command['effect'] = 'none'

        # FIXME / debuglog
        _LOGGER.warning('debug command: %s, %s', self.light_id, command)
        self.bridge.set_light(self.light_id, command)

    def turn_off(self, **kwargs):
        """ Turn the specified or all lights off. """
        command = {'on': False}

        if ATTR_TRANSITION in kwargs:
            # Transition time is in 1/10th seconds and cannot exceed
            # 900 seconds.
            command['transitiontime'] = min(9000, kwargs[ATTR_TRANSITION] * 10)

        # FIXME / debuglog
        _LOGGER.warning('debug command: %s, %s', self.light_id, command)
        self.bridge.set_light(self.light_id, command)

    def update(self):
        _LOGGER.warning('Light update called for: %s', self.light_id)
        self.bridge.update()
