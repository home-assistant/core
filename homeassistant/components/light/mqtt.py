"""
Support for MQTT lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import logging

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR,
    Light)
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_STATE, CONF_BRIGHTNESS, CONF_RGB)
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

DEFAULT_NAME = 'MQTT Light'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False
DEFAULT_BRIGHTNESS_SCALE = 255

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_BRIGHTNESS_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_BRIGHTNESS_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_BRIGHTNESS_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_RGB_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_RGB_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_RGB_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add MQTT Light."""
    config.setdefault(CONF_STATE_VALUE_TEMPLATE,
                      config.get(CONF_VALUE_TEMPLATE))
    add_devices([MqttLight(
        hass,
        config.get(CONF_NAME),
        {
            key: config.get(key) for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_BRIGHTNESS_STATE_TOPIC,
                CONF_BRIGHTNESS_COMMAND_TOPIC,
                CONF_RGB_STATE_TOPIC,
                CONF_RGB_COMMAND_TOPIC,
            )
        },
        {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            CONF_BRIGHTNESS: config.get(CONF_BRIGHTNESS_VALUE_TEMPLATE),
            CONF_RGB: config.get(CONF_RGB_VALUE_TEMPLATE)
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

    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(self, hass, name, topic, templates, qos, retain, payload,
                 optimistic, brightness_scale):
        """Initialize MQTT light."""
        self._hass = hass
        self._name = name
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._payload = payload
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
        self._optimistic_rgb = \
            optimistic or topic[CONF_RGB_STATE_TOPIC] is None
        self._optimistic_brightness = (
            optimistic or topic[CONF_BRIGHTNESS_STATE_TOPIC] is None)
        self._brightness_scale = brightness_scale
        self._state = False
        self._supported_features = 0
        self._supported_features |= (
            topic[CONF_RGB_STATE_TOPIC] is not None and SUPPORT_RGB_COLOR)
        self._supported_features |= (
            topic[CONF_BRIGHTNESS_STATE_TOPIC] is not None and
            SUPPORT_BRIGHTNESS)

        for key, tpl in list(templates.items()):
            if tpl is None:
                templates[key] = lambda value: value
            else:
                tpl.hass = hass
                templates[key] = tpl.render_with_possible_json_value

        def state_received(topic, payload, qos):
            """A new MQTT message has been received."""
            payload = templates[CONF_STATE](payload)
            if payload == self._payload['on']:
                self._state = True
            elif payload == self._payload['off']:
                self._state = False

            self.update_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            mqtt.subscribe(self._hass, self._topic[CONF_STATE_TOPIC],
                           state_received, self._qos)

        def brightness_received(topic, payload, qos):
            """A new MQTT message for the brightness has been received."""
            device_value = float(templates[CONF_BRIGHTNESS](payload))
            percent_bright = device_value / self._brightness_scale
            self._brightness = int(percent_bright * 255)
            self.update_ha_state()

        if self._topic[CONF_BRIGHTNESS_STATE_TOPIC] is not None:
            mqtt.subscribe(
                self._hass, self._topic[CONF_BRIGHTNESS_STATE_TOPIC],
                brightness_received, self._qos)
            self._brightness = 255
        elif self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
            self._brightness = 255
        else:
            self._brightness = None

        def rgb_received(topic, payload, qos):
            """A new MQTT message has been received."""
            self._rgb = [int(val) for val in
                         templates[CONF_RGB](payload).split(',')]
            self.update_ha_state()

        if self._topic[CONF_RGB_STATE_TOPIC] is not None:
            mqtt.subscribe(self._hass, self._topic[CONF_RGB_STATE_TOPIC],
                           rgb_received, self._qos)
            self._rgb = [255, 255, 255]
        if self._topic[CONF_RGB_COMMAND_TOPIC] is not None:
            self._rgb = [255, 255, 255]
        else:
            self._rgb = None

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the RGB color value."""
        return self._rgb

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

        if ATTR_RGB_COLOR in kwargs and \
           self._topic[CONF_RGB_COMMAND_TOPIC] is not None:

            mqtt.publish(self._hass, self._topic[CONF_RGB_COMMAND_TOPIC],
                         '{},{},{}'.format(*kwargs[ATTR_RGB_COLOR]),
                         self._qos, self._retain)

            if self._optimistic_rgb:
                self._rgb = kwargs[ATTR_RGB_COLOR]
                should_update = True

        if ATTR_BRIGHTNESS in kwargs and \
           self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
            percent_bright = float(kwargs[ATTR_BRIGHTNESS]) / 255
            device_brightness = int(percent_bright * self._brightness_scale)
            mqtt.publish(
                self._hass, self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC],
                device_brightness, self._qos, self._retain)

            if self._optimistic_brightness:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        mqtt.publish(self._hass, self._topic[CONF_COMMAND_TOPIC],
                     self._payload['on'], self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        mqtt.publish(self._hass, self._topic[CONF_COMMAND_TOPIC],
                     self._payload['off'], self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.update_ha_state()
