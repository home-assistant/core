"""
Support for LimitlessLED bulbs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.limitlessled/
"""
# pylint: disable=abstract-method
import logging

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_PORT)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH, ATTR_RGB_COLOR,
    ATTR_TRANSITION, EFFECT_COLORLOOP, EFFECT_WHITE, FLASH_LONG,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['limitlessled==1.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_BRIDGES = 'bridges'
CONF_GROUPS = 'groups'
CONF_NUMBER = 'number'
CONF_TYPE = 'type'
CONF_VERSION = 'version'

DEFAULT_LED_TYPE = 'rgbw'
DEFAULT_PORT = 8899
DEFAULT_TRANSITION = 0
DEFAULT_VERSION = 5

LED_TYPE = ['rgbw', 'white']

RGB_BOUNDARY = 40

WHITE = [255, 255, 255]

SUPPORT_LIMITLESSLED_WHITE = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP |
                              SUPPORT_TRANSITION)
SUPPORT_LIMITLESSLED_RGB = (SUPPORT_BRIGHTNESS | SUPPORT_EFFECT |
                            SUPPORT_FLASH | SUPPORT_RGB_COLOR |
                            SUPPORT_TRANSITION)

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
                }
            ]),
        },
    ]),
})


def rewrite_legacy(config):
    """Rewrite legacy configuration to new format."""
    bridges = config.get('bridges', [config])
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
            'host': bridge_conf.get('host'),
            'groups': groups
        })
    return {'bridges': new_bridges}


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the LimitlessLED lights."""
    from limitlessled.bridge import Bridge

    # Two legacy configuration formats are supported to
    # maintain backwards compatibility.
    config = rewrite_legacy(config)

    # Use the expanded configuration format.
    lights = []
    for bridge_conf in config.get('bridges'):
        bridge = Bridge(bridge_conf.get('host'),
                        port=bridge_conf.get('port', DEFAULT_PORT),
                        version=bridge_conf.get('version', DEFAULT_VERSION))
        for group_conf in bridge_conf.get('groups'):
            group = bridge.add_group(group_conf.get('number'),
                                     group_conf.get('name'),
                                     group_conf.get('type', DEFAULT_LED_TYPE))
            lights.append(LimitlessLEDGroup.factory(group))
    add_devices_callback(lights)


def state(new_state):
    """State decorator.

    Specify True (turn on) or False (turn off).
    """
    def decorator(function):
        """Decorator function."""
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
            # Not on and should be? Turn on.
            if not self.is_on and new_state is True:
                pipeline.on()
            # Set transition time.
            if ATTR_TRANSITION in kwargs:
                transition_time = kwargs[ATTR_TRANSITION]
            # Do group type-specific work.
            function(self, transition_time, pipeline, **kwargs)
            # Update state.
            self._is_on = new_state
            self.group.enqueue(pipeline)
            self.update_ha_state()
        return wrapper
    return decorator


class LimitlessLEDGroup(Light):
    """Representation of a LimitessLED group."""

    def __init__(self, group):
        """Initialize a group."""
        self.group = group
        self.repeating = False
        self._is_on = False
        self._brightness = None

    @staticmethod
    def factory(group):
        """Produce LimitlessLEDGroup objects."""
        from limitlessled.group.rgbw import RgbwGroup
        from limitlessled.group.white import WhiteGroup
        if isinstance(group, WhiteGroup):
            return LimitlessLEDWhiteGroup(group)
        elif isinstance(group, RgbwGroup):
            return LimitlessLEDRGBWGroup(group)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

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

    @state(False)
    def turn_off(self, transition_time, pipeline, **kwargs):
        """Turn off a group."""
        if self.is_on:
            pipeline.transition(transition_time, brightness=0.0).off()


class LimitlessLEDWhiteGroup(LimitlessLEDGroup):
    """Representation of a LimitlessLED White group."""

    def __init__(self, group):
        """Initialize White group."""
        super().__init__(group)
        # Initialize group with known values.
        self.group.on = True
        self.group.temperature = 1.0
        self.group.brightness = 0.0
        self._brightness = _to_hass_brightness(1.0)
        self._temperature = _to_hass_temperature(self.group.temperature)
        self.group.on = False

    @property
    def color_temp(self):
        """Return the temperature property."""
        return self._temperature

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LIMITLESSLED_WHITE

    @state(True)
    def turn_on(self, transition_time, pipeline, **kwargs):
        """Turn on (or adjust property of) a group."""
        # Check arguments.
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_COLOR_TEMP in kwargs:
            self._temperature = kwargs[ATTR_COLOR_TEMP]
        # Set up transition.
        pipeline.transition(transition_time,
                            brightness=_from_hass_brightness(
                                self._brightness),
                            temperature=_from_hass_temperature(
                                self._temperature))


class LimitlessLEDRGBWGroup(LimitlessLEDGroup):
    """Representation of a LimitlessLED RGBW group."""

    def __init__(self, group):
        """Initialize RGBW group."""
        super().__init__(group)
        # Initialize group with known values.
        self.group.on = True
        self.group.white()
        self._color = WHITE
        self.group.brightness = 0.0
        self._brightness = _to_hass_brightness(1.0)
        self.group.on = False

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LIMITLESSLED_RGB

    @state(True)
    def turn_on(self, transition_time, pipeline, **kwargs):
        """Turn on (or adjust property of) a group."""
        from limitlessled.presets import COLORLOOP
        # Check arguments.
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_RGB_COLOR in kwargs:
            self._color = kwargs[ATTR_RGB_COLOR]
        # White is a special case.
        if min(self._color) > 256 - RGB_BOUNDARY:
            pipeline.white()
            self._color = WHITE
        # Set up transition.
        pipeline.transition(transition_time,
                            brightness=_from_hass_brightness(
                                self._brightness),
                            color=_from_hass_color(self._color))
        # Flash.
        if ATTR_FLASH in kwargs:
            duration = 0
            if kwargs[ATTR_FLASH] == FLASH_LONG:
                duration = 1
            pipeline.flash(duration=duration)
        # Add effects.
        if ATTR_EFFECT in kwargs:
            if kwargs[ATTR_EFFECT] == EFFECT_COLORLOOP:
                self.repeating = True
                pipeline.append(COLORLOOP)
            if kwargs[ATTR_EFFECT] == EFFECT_WHITE:
                pipeline.white()
                self._color = WHITE


def _from_hass_temperature(temperature):
    """Convert Home Assistant color temperature units to percentage."""
    return (temperature - 154) / 346


def _to_hass_temperature(temperature):
    """Convert percentage to Home Assistant color temperature units."""
    return int(temperature * 346) + 154


def _from_hass_brightness(brightness):
    """Convert Home Assistant brightness units to percentage."""
    return brightness / 255


def _to_hass_brightness(brightness):
    """Convert percentage to Home Assistant brightness units."""
    return int(brightness * 255)


def _from_hass_color(color):
    """Convert Home Assistant RGB list to Color tuple."""
    from limitlessled import Color
    return Color(*tuple(color))


def _to_hass_color(color):
    """Convert from Color tuple to Home Assistant RGB list."""
    return list([int(c) for c in color])
