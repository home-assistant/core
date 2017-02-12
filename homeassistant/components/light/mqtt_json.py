"""
Support for MQTT JSON lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt_json/
"""

import logging
import json
import voluptuous as vol

import homeassistant.util.color as color_util
import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_TRANSITION, PLATFORM_SCHEMA,
    ATTR_FLASH, ATTR_XY_COLOR, ATTR_COLOR_TEMP, ATTR_EFFECT, FLASH_LONG,
    FLASH_SHORT, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_FLASH,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, SUPPORT_EFFECT, SUPPORT_XY_COLOR,
    Light)
from homeassistant.const import (CONF_NAME, CONF_OPTIMISTIC, CONF_RGB, CONF_XY,
                                 CONF_BRIGHTNESS, CONF_COLOR_TEMP,
                                 CONF_TRANSITION, CONF_FLASH)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mqtt_json'

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT JSON Light'
DEFAULT_OPTIMISTIC = False
DEFAULT_BRIGHTNESS = False
DEFAULT_COLOR_TEMP = False
DEFAULT_TRANSITION = False
DEFAULT_FLASH = False
DEFAULT_FLASH_TIME_SHORT = 2
DEFAULT_FLASH_TIME_LONG = 10

CONF_COLOR_SPACE = 'color_space'
CONF_EFFECT_LIST = 'effect_list'
CONF_FLASH_TIME_SHORT = 'flash_time_short'
CONF_FLASH_TIME_LONG = 'flash_time_long'

# Stealing some of these from the base MQTT configs.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_QOS, default=mqtt.DEFAULT_QOS):
        vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
    vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS): cv.boolean,
    vol.Optional(CONF_COLOR_SPACE): vol.In([CONF_RGB, CONF_XY]),
    vol.Optional(CONF_COLOR_TEMP, default=DEFAULT_COLOR_TEMP): cv.boolean,
    vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.boolean,
    vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_FLASH, default=DEFAULT_FLASH): cv.boolean,
    vol.Optional(CONF_FLASH_TIME_SHORT, default=DEFAULT_FLASH_TIME_SHORT):
        cv.positive_int,
    vol.Optional(CONF_FLASH_TIME_LONG, default=DEFAULT_FLASH_TIME_LONG):
        cv.positive_int
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a MQTT JSON Light."""
    add_devices([MqttJson(
        hass,
        config.get(CONF_NAME),
        {
            key: config.get(key)
            for key in (CONF_STATE_TOPIC, CONF_COMMAND_TOPIC)
        },
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_OPTIMISTIC),
        {
            key: config.get(key) for key in (
                CONF_BRIGHTNESS,
                CONF_COLOR_TEMP,
                CONF_TRANSITION,
                CONF_FLASH,
            )
        },
        config.get(CONF_COLOR_SPACE),
        config.get(CONF_EFFECT_LIST),
        {
            key: config.get(key)
            for key in (CONF_FLASH_TIME_SHORT, CONF_FLASH_TIME_LONG)
        }
    )])


class MqttJson(Light):
    """Representation of a MQTT JSON light."""

    def __init__(self, hass, name, topic, qos, retain, optimistic,
                 supported_features, color_space, effect_list, flash_times):
        """Initialize MQTT JSON light."""
        self._hass = hass
        self._name = name
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None

        self._state = False
        self._color_space = color_space
        self._flash_times = flash_times
        self._effect_list = effect_list
        self._effect = None
        self._supported_features = 0
        self._supported_features |= (
            supported_features[CONF_BRIGHTNESS] and
            SUPPORT_BRIGHTNESS)
        self._supported_features |= (
            supported_features[CONF_COLOR_TEMP] and
            SUPPORT_COLOR_TEMP)
        self._supported_features |= (
            supported_features[CONF_FLASH] and SUPPORT_FLASH)
        self._supported_features |= (
            supported_features[CONF_TRANSITION] and
            SUPPORT_TRANSITION)
        self._supported_features |= (
            (self._color_space == CONF_RGB or self._color_space == CONF_XY) and
            SUPPORT_RGB_COLOR | SUPPORT_XY_COLOR)
        self._supported_features |= (self._effect_list is not None and
                                     SUPPORT_EFFECT)

        if self._supported_features & SUPPORT_BRIGHTNESS:
            self._brightness = 255
        else:
            self._brightness = None

        if self._supported_features & SUPPORT_RGB_COLOR:
            self._rgb = (0, 0, 0)
        else:
            self._rgb = None

        if self._supported_features & SUPPORT_XY_COLOR:
            self._xy = (0, 0)
        else:
            self._xy = None

        if self._supported_features & SUPPORT_COLOR_TEMP:
            self._color_temp = color_util.HASS_COLOR_MIN
        else:
            self._color_temp = None

        def state_received(topic, payload, qos):
            """A new MQTT message has been received."""
            values = json.loads(payload)

            # read state
            if values['state'] == 'ON':
                self._state = True
            elif values['state'] == 'OFF':
                self._state = False
            else:
                _LOGGER.warning('Invalid state value received')

            # read brightness
            if self._supported_features & SUPPORT_BRIGHTNESS:
                try:
                    self._brightness = int(values['brightness'])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning('Invalid brightness value received')

            # read rgb color
            if self._color_space == CONF_RGB:
                try:
                    red = int(values['color']['r'])
                    green = int(values['color']['g'])
                    blue = int(values['color']['b'])

                    self._rgb = (red, green, blue)
                    xyb = color_util.color_RGB_to_xy(red, green, blue)
                    self._xy = (xyb[0], xyb[1])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid rgb value received")

            # read xy color
            if self._color_space == CONF_XY:
                try:
                    x = float(values['color']['x'])
                    y = float(values['color']['y'])

                    self._xy = (x, y)
                    self._rgb = tuple(color_util.color_xy_brightness_to_RGB(
                        x, y, 255))
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid xy value received")

            # read color temp
            if self._supported_features & SUPPORT_COLOR_TEMP:
                try:
                    self._color_temp = int(values['color_temp'])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid color temp value received")

            # read effect
            if self._supported_features & SUPPORT_EFFECT:
                try:
                    effect = values['effect']

                    # validate effect value
                    if effect in self._effect_list:
                        self._effect = effect
                    else:
                        _LOGGER.warning('Invalid effect value received')
                except KeyError:
                    pass

            self.update_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            mqtt.subscribe(self._hass, self._topic[CONF_STATE_TOPIC],
                           state_received, self._qos)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the RGB color value."""
        return self._rgb

    @property
    def xy_color(self):
        """Return the XY color value."""
        return self._xy

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._color_temp

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def should_poll(self):
        """No polling needed for a MQTT light."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def turn_on(self, **kwargs):
        """Turn the device on."""
        should_update = False

        message = {'state': 'ON'}

        if ATTR_BRIGHTNESS in kwargs and \
           self._supported_features & SUPPORT_BRIGHTNESS:
            message['brightness'] = int(kwargs[ATTR_BRIGHTNESS])

            if self._optimistic:
                self._brightness = int(kwargs[ATTR_BRIGHTNESS])
                should_update = True

        if ATTR_RGB_COLOR in kwargs and \
           self._supported_features & SUPPORT_RGB_COLOR:
            rgb = kwargs[ATTR_RGB_COLOR]
            xyb = color_util.color_RGB_to_xy(rgb[0], rgb[1], rgb[2])
            if self._color_space == CONF_RGB:
                message['color'] = {'r': rgb[0], 'g': rgb[1], 'b': rgb[2]}
            else:
                message['color'] = {'x': xyb[0], 'y': xyb[1]}

            if self._optimistic:
                self._rgb = tuple(rgb)
                self._xy = (xyb[0], xyb[1])
                should_update = True

        if ATTR_XY_COLOR in kwargs and \
           self._supported_features & SUPPORT_XY_COLOR:
            xy = kwargs[ATTR_XY_COLOR]
            rgb = color_util.color_xy_brightness_to_RGB(xy[0], xy[1], 255)
            if self._color_space == CONF_XY:
                message['color'] = {'x': xy[0], 'y': xy[1]}
            else:
                message['color'] = {'r': rgb[0], 'g': rgb[1], 'b': rgb[2]}

            if self._optimistic:
                self._xy = tuple(xy)
                self._rgb = tuple(rgb)
                should_update = True

        if ATTR_COLOR_TEMP in kwargs and \
           self._supported_features & SUPPORT_COLOR_TEMP:
            message['color_temp'] = int(kwargs[ATTR_COLOR_TEMP])

            if self._optimistic:
                self._color_temp = int(kwargs[ATTR_COLOR_TEMP])
                should_update = True

        if ATTR_TRANSITION in kwargs and \
           self._supported_features & SUPPORT_TRANSITION:
            message['transition'] = kwargs[ATTR_TRANSITION]

        if ATTR_EFFECT in kwargs and self._supported_features & SUPPORT_EFFECT:
            effect = kwargs[ATTR_EFFECT]

            if effect in self._effect_list:
                message['effect'] = effect
                if self._optimistic:
                    self._effect = effect
                    should_update = True
            else:
                _LOGGER.warning('Invalid effect value passed')

        if ATTR_FLASH in kwargs and self._supported_features & SUPPORT_FLASH:
            flash = kwargs[ATTR_FLASH]

            if flash == FLASH_LONG:
                message['flash'] = self._flash_times[CONF_FLASH_TIME_LONG]
            elif flash == FLASH_SHORT:
                message['flash'] = self._flash_times[CONF_FLASH_TIME_SHORT]

        mqtt.publish(self._hass, self._topic[CONF_COMMAND_TOPIC],
                     json.dumps(message), self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        message = {'state': 'OFF'}

        if ATTR_TRANSITION in kwargs and \
           self._supported_features & SUPPORT_TRANSITION:
            message['transition'] = kwargs[ATTR_TRANSITION]

        mqtt.publish(self._hass, self._topic[CONF_COMMAND_TOPIC],
                     json.dumps(message), self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = False
            self.schedule_update_ha_state()
