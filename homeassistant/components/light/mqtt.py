"""
homeassistant.components.light.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import logging
from functools import partial

import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, Light)
from homeassistant.util.template import render_with_possible_json_value

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MQTT Light'
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False

DEPENDENCIES = ['mqtt']


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Light. """

    if config.get('command_topic') is None:
        _LOGGER.error("Missing required variable: command_topic")
        return False

    add_devices_callback([MqttLight(
        hass,
        config.get('name', DEFAULT_NAME),
        {key: config.get(key) for key in
         (typ + topic
          for typ in ('', 'brightness_', 'rgb_')
          for topic in ('state_topic', 'command_topic'))},
        {key: config.get(key + '_value_template')
         for key in ('state', 'brightness', 'rgb')},
        config.get('qos', DEFAULT_QOS),
        {
            'on': config.get('payload_on', DEFAULT_PAYLOAD_ON),
            'off': config.get('payload_off', DEFAULT_PAYLOAD_OFF)
        },
        config.get('optimistic', DEFAULT_OPTIMISTIC))])


class MqttLight(Light):
    """ Provides a MQTT light. """

    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(self, hass, name, topic, templates, qos, payload, optimistic):

        self._hass = hass
        self._name = name
        self._topic = topic
        self._qos = qos
        self._payload = payload
        self._optimistic = optimistic or topic["state_topic"] is None
        self._optimistic_rgb = optimistic or topic["rgb_state_topic"] is None
        self._optimistic_brightness = (optimistic or
                                       topic["brightness_state_topic"] is None)
        self._state = False

        templates = {key: ((lambda value: value) if tpl is None else
                           partial(render_with_possible_json_value, hass, tpl))
                     for key, tpl in templates.items()}

        def state_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            payload = templates['state'](payload)
            if payload == self._payload["on"]:
                self._state = True
            elif payload == self._payload["off"]:
                self._state = False

            self.update_ha_state()

        if self._topic["state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["state_topic"],
                           state_received, self._qos)

        def brightness_received(topic, payload, qos):
            """ A new MQTT message for the brightness has been received. """
            self._brightness = int(templates['brightness'](payload))
            self.update_ha_state()

        if self._topic["brightness_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["brightness_state_topic"],
                           brightness_received, self._qos)
            self._brightness = 255
        else:
            self._brightness = None

        def rgb_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            self._rgb = [int(val) for val in
                         templates['rgb'](payload).split(',')]
            self.update_ha_state()

        if self._topic["rgb_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["rgb_state_topic"],
                           rgb_received, self._qos)
            self._rgb = [255, 255, 255]
        else:
            self._rgb = None

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self._brightness

    @property
    def rgb_color(self):
        """ RGB color value. """
        return self._rgb

    @property
    def should_poll(self):
        """ No polling needed for a MQTT light. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        should_update = False

        if ATTR_RGB_COLOR in kwargs and \
           self._topic["rgb_command_topic"] is not None:
            mqtt.publish(self._hass, self._topic["rgb_command_topic"],
                         "{},{},{}".format(*kwargs[ATTR_RGB_COLOR]), self._qos)

            if self._optimistic_rgb:
                self._rgb = kwargs[ATTR_RGB_COLOR]
                should_update = True

        if ATTR_BRIGHTNESS in kwargs and \
           self._topic["brightness_command_topic"] is not None:

            mqtt.publish(self._hass, self._topic["brightness_command_topic"],
                         kwargs[ATTR_BRIGHTNESS], self._qos)

            if self._optimistic_brightness:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        mqtt.publish(self._hass, self._topic["command_topic"],
                     self._payload["on"], self._qos)

        if self._optimistic:
            # optimistically assume that switch has changed state
            self._state = True
            should_update = True

        if should_update:
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        mqtt.publish(self._hass, self._topic["command_topic"],
                     self._payload["off"], self._qos)

        if self._optimistic:
            # optimistically assume that switch has changed state
            self._state = False
            self.update_ha_state()
