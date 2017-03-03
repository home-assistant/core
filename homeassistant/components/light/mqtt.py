"""
Support for MQTT lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_COLOR_TEMP, SUPPORT_BRIGHTNESS,
    SUPPORT_RGB_COLOR, SUPPORT_COLOR_TEMP, Light)
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_STATE, CONF_BRIGHTNESS, CONF_RGB,
    CONF_COLOR_TEMP)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_STATE_VALUE_TEMPLATE = 'state_value_template'
CONF_BRIGHTNESS_STATE_TOPIC = 'brightness_state_topic'
CONF_BRIGHTNESS_COMMAND_TOPIC = 'brightness_command_topic'
CONF_BRIGHTNESS_VALUE_TEMPLATE = 'brightness_value_template'
CONF_RGB_STATE_TOPIC = 'rgb_state_topic'
CONF_RGB_COMMAND_TOPIC = 'rgb_command_topic'
CONF_RGB_VALUE_TEMPLATE = 'rgb_value_template'
CONF_BRIGHTNESS_SCALE = 'brightness_scale'
CONF_COLOR_TEMP_STATE_TOPIC = 'color_temp_state_topic'
CONF_COLOR_TEMP_COMMAND_TOPIC = 'color_temp_command_topic'
CONF_COLOR_TEMP_VALUE_TEMPLATE = 'color_temp_value_template'

DEFAULT_NAME = 'MQTT Light'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False
DEFAULT_BRIGHTNESS_SCALE = 255

# Defines to select the control to turn the device on and off
CONTROL_STATE = 0
CONTROL_BRIGHTNESS = 1
CONTROL_RGB = 2

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_BRIGHTNESS_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_BRIGHTNESS_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_BRIGHTNESS_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_COLOR_TEMP_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_COLOR_TEMP_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_COLOR_TEMP_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_RGB_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_RGB_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_RGB_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Add MQTT Light."""
    config.setdefault(
        CONF_STATE_VALUE_TEMPLATE, config.get(CONF_VALUE_TEMPLATE))

    yield from async_add_devices([MqttLight(
        config.get(CONF_NAME),
        {
            key: config.get(key) for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_BRIGHTNESS_STATE_TOPIC,
                CONF_BRIGHTNESS_COMMAND_TOPIC,
                CONF_RGB_STATE_TOPIC,
                CONF_RGB_COMMAND_TOPIC,
                CONF_COLOR_TEMP_STATE_TOPIC,
                CONF_COLOR_TEMP_COMMAND_TOPIC
            )
        },
        {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            CONF_BRIGHTNESS: config.get(CONF_BRIGHTNESS_VALUE_TEMPLATE),
            CONF_RGB: config.get(CONF_RGB_VALUE_TEMPLATE),
            CONF_COLOR_TEMP: config.get(CONF_COLOR_TEMP_VALUE_TEMPLATE)
        },
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        {
            'on': config.get(CONF_PAYLOAD_ON),
            'off': config.get(CONF_PAYLOAD_OFF),
        },
        config.get(CONF_OPTIMISTIC),
        config.get(CONF_BRIGHTNESS_SCALE),
    )])


class MqttLight(Light):
    """MQTT light."""

    def __init__(self, name, topic, templates, qos, retain, payload,
                 optimistic, brightness_scale):
        """Initialize MQTT light."""
        self._name = name
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._payload = payload
        self._templates = templates
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None

        self._optimistic_rgb = \
            optimistic or topic[CONF_RGB_STATE_TOPIC] is None
        self._optimistic_brightness = (
            optimistic or topic[CONF_BRIGHTNESS_STATE_TOPIC] is None)
        self._optimistic_color_temp = (
            optimistic or topic[CONF_COLOR_TEMP_STATE_TOPIC] is None)

        if topic[CONF_COMMAND_TOPIC] is not None:
            self._state_control = CONTROL_STATE
            self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
            self._last_value = None # Last value is not used if a dedicated
             # on/off topic is available
        elif topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
            self._state_control = CONTROL_BRIGHTNESS
            self._optimistic = self._optimistic_brightness
            self._last_value = 255
        elif topic[CONF_RGB_COMMAND_TOPIC] is not None:
            self._state_control = CONTROL_RGB
            self._optimistic = self._optimistic_rgb
            self._last_value = [255, 255, 255]
        else:
            raise RuntimeError("No command topic set.")


        self._brightness_scale = brightness_scale
        self._state = False
        self._brightness = None
        self._rgb = None
        self._color_temp = None
        self._supported_features = 0
        self._supported_features |= (
            topic[CONF_RGB_COMMAND_TOPIC] is not None and SUPPORT_RGB_COLOR)
        self._supported_features |= (
            topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None and
            SUPPORT_BRIGHTNESS)
        self._supported_features |= (
            topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None and
            SUPPORT_COLOR_TEMP)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method is a coroutine.
        """
        templates = {}
        for key, tpl in list(self._templates.items()):
            if tpl is None:
                templates[key] = lambda value: value
            else:
                tpl.hass = self.hass
                templates[key] = tpl.async_render_with_possible_json_value

        @callback
        def state_received(topic, payload, qos):
            """A new MQTT message has been received."""
            payload = templates[CONF_STATE](payload)
            if payload == self._payload['on']:
                self._state = True
            elif payload == self._payload['off']:
                self._state = False
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_STATE_TOPIC], state_received,
                self._qos)

        @callback
        def brightness_received(topic, payload, qos):
            """A new MQTT message for the brightness has been received."""
            device_value = float(templates[CONF_BRIGHTNESS](payload))
            percent_bright = device_value / self._brightness_scale
            self._brightness = int(percent_bright * 255)
            if self._state_control == CONTROL_BRIGHTNESS:
                self._state = self._brightness != 0
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_BRIGHTNESS_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_BRIGHTNESS_STATE_TOPIC],
                brightness_received, self._qos)
            self._brightness = 255
        elif self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
            self._brightness = 255
        else:
            self._brightness = None

        @callback
        def rgb_received(topic, payload, qos):
            """A new MQTT message has been received."""
            self._rgb = [int(val) for val in
                         templates[CONF_RGB](payload).split(',')]
            if self._state_control == CONTROL_RGB:
                self._state = self._rgb != [0, 0, 0]
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_RGB_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_RGB_STATE_TOPIC], rgb_received,
                self._qos)
            self._rgb = [255, 255, 255]
        if self._topic[CONF_RGB_COMMAND_TOPIC] is not None:
            self._rgb = [255, 255, 255]
        else:
            self._rgb = None

        @callback
        def color_temp_received(topic, payload, qos):
            """A new MQTT message for color temp has been received."""
            self._color_temp = int(templates[CONF_COLOR_TEMP](payload))
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_COLOR_TEMP_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_COLOR_TEMP_STATE_TOPIC],
                color_temp_received, self._qos)
            self._color_temp = 150
        if self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None:
            self._color_temp = 150
        else:
            self._color_temp = None

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the RGB color value."""
        return self._rgb

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

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

    def _publish_brightness(self, brightness):
        """ Rescale brightness value to match device brightness range and
            publish MQTT message to set this value. """
        percent_bright = float(brightness) / 255
        device_brightness = int(percent_bright * self._brightness_scale)
        mqtt.async_publish(
            self.hass, self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC],
            device_brightness, self._qos, self._retain)

    def _publish_rgb(self, r, g, b):
        """ Publish RGB value via MQTT """
        mqtt.async_publish(self.hass, self._topic[CONF_RGB_COMMAND_TOPIC],
                     '{},{},{}'.format(r, g, b),
                      self._qos, self._retain)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False

        if ATTR_RGB_COLOR in kwargs and \
           self._topic[CONF_RGB_COMMAND_TOPIC] is not None:
            self._publish_rgb(*kwargs[ATTR_RGB_COLOR])
            if self._optimistic_rgb:
                self._rgb = kwargs[ATTR_RGB_COLOR]
                should_update = True

        if ATTR_BRIGHTNESS in kwargs and \
           self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
            self._publish_brightness(kwargs[ATTR_BRIGHTNESS])
            if self._optimistic_brightness:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        if ATTR_COLOR_TEMP in kwargs and \
           self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None:
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            mqtt.async_publish(
                self.hass, self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC],
                color_temp, self._qos, self._retain)
            if self._optimistic_color_temp:
                self._color_temp = kwargs[ATTR_COLOR_TEMP]
                should_update = True

        if self._state_control == CONTROL_STATE:
            mqtt.async_publish(self.hass, self._topic[CONF_COMMAND_TOPIC],
                         self._payload['on'], self._qos, self._retain)
        elif self._state_control == CONTROL_BRIGHTNESS:
            if ATTR_BRIGHTNESS not in kwargs:
                self._publish_brightness(self._last_value)
        elif self._state_control == CONTROL_RGB:
            if ATTR_RGB_COLOR not in kwargs:
                self._publish_rgb(*self._last_value)

        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        if self._state_control == CONTROL_STATE:
            mqtt.async_publish(self.hass, self._topic[CONF_COMMAND_TOPIC],
                         self._payload['off'], self._qos, self._retain)
        elif self._state_control == CONTROL_BRIGHTNESS:
            self._last_value = self._brightness
            self._publish_brightness(0)
        elif self._state_control == CONTROL_RGB:
            self._last_value = self._rgb
            self._publish_rgb(0, 0, 0)

        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.hass.async_add_job(self.async_update_ha_state())
