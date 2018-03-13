"""
Support for LimitlessLED bulbs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.limitlessled/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_TYPE, STATE_ON)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH, ATTR_RGB_COLOR,
    ATTR_TRANSITION, EFFECT_COLORLOOP, EFFECT_WHITE, FLASH_LONG,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.color import color_temperature_mired_to_kelvin
from homeassistant.helpers.restore_state import async_get_last_state

REQUIREMENTS = ['limitlessled==1.1.0']

_LOGGER = logging.getLogger(__name__)

CONF_BRIDGES = 'bridges'
CONF_GROUPS = 'groups'
CONF_NUMBER = 'number'
CONF_VERSION = 'version'
CONF_FADE = 'fade'

DEFAULT_LED_TYPE = 'rgbw'
DEFAULT_PORT = 5987
DEFAULT_TRANSITION = 0
DEFAULT_VERSION = 6
DEFAULT_FADE = False

LED_TYPE = ['rgbw', 'rgbww', 'white', 'bridge-led', 'dimmer']

EFFECT_NIGHT = 'night'

RGB_BOUNDARY = 40

WHITE = [255, 255, 255]

SUPPORT_LIMITLESSLED_WHITE = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP |
                              SUPPORT_TRANSITION)
SUPPORT_LIMITLESSLED_DIMMER = (SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION)
SUPPORT_LIMITLESSLED_RGB = (SUPPORT_BRIGHTNESS | SUPPORT_EFFECT |
                            SUPPORT_FLASH | SUPPORT_RGB_COLOR |
                            SUPPORT_TRANSITION)
SUPPORT_LIMITLESSLED_RGBWW = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP |
                              SUPPORT_EFFECT | SUPPORT_FLASH |
                              SUPPORT_RGB_COLOR | SUPPORT_TRANSITION)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_BRIDGES): vol.All(cv.ensure_list, [
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_VERSION,
                         default=DEFAULT_VERSION): cv.positive_int,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Required(CONF_GROUPS):  vol.All(cv.ensure_list, [
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Optional(CONF_TYPE, default=DEFAULT_LED_TYPE):
                        vol.In(LED_TYPE),
                    vol.Required(CONF_NUMBER): cv.positive_int,
                    vol.Optional(CONF_FADE, default=DEFAULT_FADE): cv.boolean,
                }
            ]),
        },
    ]),
})


def rewrite_legacy(config):
    """Rewrite legacy configuration to new format."""
    bridges = config.get(CONF_BRIDGES, [config])
    new_bridges = []
    for bridge_conf in bridges:
        groups = []
        if 'groups' in bridge_conf:
            groups = bridge_conf['groups']
        else:
            _LOGGER.warning("Legacy configuration format detected")
            for i in range(1, 5):
                name_key = 'group_%d_name' % i
                if name_key in bridge_conf:
                    groups.append({
                        'number': i,
                        'type':  bridge_conf.get('group_%d_type' % i,
                                                 DEFAULT_LED_TYPE),
                        'name': bridge_conf.get(name_key)
                    })
        new_bridges.append({
            'host': bridge_conf.get(CONF_HOST),
            'version': bridge_conf.get(CONF_VERSION),
            'port': bridge_conf.get(CONF_PORT),
            'groups': groups
        })
    return {'bridges': new_bridges}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the LimitlessLED lights."""
    from limitlessled.bridge import Bridge

    # Two legacy configuration formats are supported to maintain backwards
    # compatibility.
    config = rewrite_legacy(config)

    # Use the expanded configuration format.
    lights = []
    for bridge_conf in config.get(CONF_BRIDGES):
        bridge = Bridge(bridge_conf.get(CONF_HOST),
                        port=bridge_conf.get(CONF_PORT, DEFAULT_PORT),
                        version=bridge_conf.get(CONF_VERSION, DEFAULT_VERSION))
        for group_conf in bridge_conf.get(CONF_GROUPS):
            group = bridge.add_group(
                group_conf.get(CONF_NUMBER),
                group_conf.get(CONF_NAME),
                group_conf.get(CONF_TYPE, DEFAULT_LED_TYPE))
            lights.append(LimitlessLEDGroup(group, {
                'fade': group_conf[CONF_FADE]
            }))
    add_devices(lights)


def state(new_state):
    """State decorator.

    Specify True (turn on) or False (turn off).
    """
    def decorator(function):
        """Set up the decorator function."""
        # pylint: disable=no-member,protected-access
        def wrapper(self, **kwargs):
            """Wrap a group state change."""
            from limitlessled.pipeline import Pipeline
            pipeline = Pipeline()
            transition_time = DEFAULT_TRANSITION
            # Stop any repeating pipeline.
            if self.repeating:
                self.repeating = False
                self.group.stop()
            # Set transition time.
            if ATTR_TRANSITION in kwargs:
                transition_time = int(kwargs[ATTR_TRANSITION])
            # Do group type-specific work.
            function(self, transition_time, pipeline, **kwargs)
            # Update state.
            self._is_on = new_state
            self.group.enqueue(pipeline)
            self.schedule_update_ha_state()
        return wrapper
    return decorator


class LimitlessLEDGroup(Light):
    """Representation of a LimitessLED group."""

    def __init__(self, group, config):
        """Initialize a group."""
        from limitlessled.group.rgbw import RgbwGroup
        from limitlessled.group.white import WhiteGroup
        from limitlessled.group.dimmer import DimmerGroup
        from limitlessled.group.rgbww import RgbwwGroup
        if isinstance(group, WhiteGroup):
            self._supported = SUPPORT_LIMITLESSLED_WHITE
            self._effect_list = [EFFECT_NIGHT]
        elif isinstance(group, DimmerGroup):
            self._supported = SUPPORT_LIMITLESSLED_DIMMER
            self._effect_list = []
        elif isinstance(group, RgbwGroup):
            self._supported = SUPPORT_LIMITLESSLED_RGB
            self._effect_list = [EFFECT_COLORLOOP, EFFECT_NIGHT, EFFECT_WHITE]
        elif isinstance(group, RgbwwGroup):
            self._supported = SUPPORT_LIMITLESSLED_RGBWW
            self._effect_list = [EFFECT_COLORLOOP, EFFECT_NIGHT, EFFECT_WHITE]

        self.group = group
        self.config = config
        self.repeating = False
        self._is_on = False
        self._brightness = None
        self._temperature = None
        self._color = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Called when entity is about to be added to hass."""
        last_state = yield from async_get_last_state(self.hass, self.entity_id)
        if last_state:
            self._is_on = (last_state.state == STATE_ON)
            self._brightness = last_state.attributes.get('brightness')
            self._temperature = last_state.attributes.get('color_temp')
            self._color = last_state.attributes.get('rgb_color')

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def assumed_state(self):
        """Return True because unable to access real state of the entity."""
        return True

    @property
    def name(self):
        """Return the name of the group."""
        return self.group.name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    @property
    def brightness(self):
        """Return the brightness property."""
        return self._brightness

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return 154

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return 370

    @property
    def color_temp(self):
        """Return the temperature property."""
        return self._temperature

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._color

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported

    @property
    def effect_list(self):
        """Return the list of supported effects for this light."""
        return self._effect_list

    # pylint: disable=arguments-differ
    @state(False)
    def turn_off(self, transition_time, pipeline, **kwargs):
        """Turn off a group."""
        if self.config[CONF_FADE]:
            pipeline.transition(transition_time, brightness=0.0)
        pipeline.off()

    # pylint: disable=arguments-differ
    @state(True)
    def turn_on(self, transition_time, pipeline, **kwargs):
        """Turn on (or adjust property of) a group."""
        # The night effect does not need a turned on light
        if kwargs.get(ATTR_EFFECT) == EFFECT_NIGHT:
            if EFFECT_NIGHT in self._effect_list:
                pipeline.night_light()
            return

        pipeline.on()

        # Set up transition.
        args = {}
        if self.config[CONF_FADE] and not self.is_on and self._brightness:
            args['brightness'] = self.limitlessled_brightness()

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            args['brightness'] = self.limitlessled_brightness()

        if ATTR_RGB_COLOR in kwargs and self._supported & SUPPORT_RGB_COLOR:
            self._color = kwargs[ATTR_RGB_COLOR]
            # White is a special case.
            if min(self._color) > 256 - RGB_BOUNDARY:
                pipeline.white()
                self._color = WHITE
            else:
                args['color'] = self.limitlessled_color()

        if ATTR_COLOR_TEMP in kwargs:
            if self._supported & SUPPORT_RGB_COLOR:
                pipeline.white()
            self._color = WHITE
            if self._supported & SUPPORT_COLOR_TEMP:
                self._temperature = kwargs[ATTR_COLOR_TEMP]
                args['temperature'] = self.limitlessled_temperature()

        if args:
            pipeline.transition(transition_time, **args)

        # Flash.
        if ATTR_FLASH in kwargs and self._supported & SUPPORT_FLASH:
            duration = 0
            if kwargs[ATTR_FLASH] == FLASH_LONG:
                duration = 1
            pipeline.flash(duration=duration)

        # Add effects.
        if ATTR_EFFECT in kwargs and self._effect_list:
            if kwargs[ATTR_EFFECT] == EFFECT_COLORLOOP:
                from limitlessled.presets import COLORLOOP
                self.repeating = True
                pipeline.append(COLORLOOP)
            if kwargs[ATTR_EFFECT] == EFFECT_WHITE:
                pipeline.white()
                self._color = WHITE

    def limitlessled_temperature(self):
        """Convert Home Assistant color temperature units to percentage."""
        max_kelvin = color_temperature_mired_to_kelvin(self.min_mireds)
        min_kelvin = color_temperature_mired_to_kelvin(self.max_mireds)
        width = max_kelvin - min_kelvin
        kelvin = color_temperature_mired_to_kelvin(self._temperature)
        temperature = (kelvin - min_kelvin) / width
        return max(0, min(1, temperature))

    def limitlessled_brightness(self):
        """Convert Home Assistant brightness units to percentage."""
        return self._brightness / 255

    def limitlessled_color(self):
        """Convert Home Assistant RGB list to Color tuple."""
        from limitlessled import Color
        return Color(*tuple(self._color))
