"""
homeassistant.components.light.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import logging

import homeassistant.util.color as color_util
import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (Light,
                                            ATTR_BRIGHTNESS, ATTR_RGB_COLOR)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Light"
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_ON = "on"
DEFAULT_PAYLOAD_OFF = "off"
DEFAULT_RGB_PATTERN = "%d,%d,%d"
DEFAULT_OPTIMISTIC = False

DEPENDENCIES = ['mqtt']

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Light. """

    if config.get('command_topic') is None:
        _LOGGER.error("Missing required variable: command_topic")
        return False

    add_devices_callback([MqttLight(
        hass,
        config.get('name', DEFAULT_NAME),
        {"state_topic": config.get('state_topic'),
         "command_topic": config.get('command_topic'),
         "brightness_state_topic": config.get('brightness_state_topic'),
         "brightness_command_topic":
             config.get('brightness_command_topic'),
         "rgb_state_topic": config.get('rgb_state_topic'),
         "rgb_command_topic": config.get('rgb_command_topic')},
        config.get('rgb', None),
        config.get('qos', DEFAULT_QOS),
        {"on": config.get('payload_on', DEFAULT_PAYLOAD_ON),
         "off": config.get('payload_off', DEFAULT_PAYLOAD_OFF)},
        config.get('brightness'),
        config.get('optimistic', DEFAULT_OPTIMISTIC))])

# pylint: disable=too-many-instance-attributes


class MqttLight(Light):
    """ Provides a MQTT light. """

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name,
                 topic,
                 rgb, qos,
                 payload,
                 brightness, optimistic):

        self._hass = hass
        self._name = name
        self._topic = topic
        self._rgb = rgb
        self._qos = qos
        self._payload = payload
        self._brightness = brightness
        self._optimistic = optimistic
        self._state = False
        self._xy = None

        def message_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            if payload == self._payload["on"]:
                self._state = True
            elif payload == self._payload["off"]:
                self._state = False

            self.update_ha_state()

        if self._topic["state_topic"] is None:
            # force optimistic mode
            self._optimistic = True
        else:
            # Subscribe the state_topic
            mqtt.subscribe(self._hass, self._topic["state_topic"],
                           message_received, self._qos)

        def brightness_received(topic, payload, qos):
            """ A new MQTT message for the brightness has been received. """
            self._brightness = int(payload)
            self.update_ha_state()

        def rgb_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            self._rgb = [int(val) for val in payload.split(',')]
            self._xy = color_util.color_RGB_to_xy(int(self._rgb[0]),
                                                  int(self._rgb[1]),
                                                  int(self._rgb[2]))
            self.update_ha_state()

        if self._topic["brightness_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["brightness_state_topic"],
                           brightness_received, self._qos)
            self._brightness = 255
        else:
            self._brightness = None

        if self._topic["rgb_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["rgb_state_topic"],
                           rgb_received, self._qos)
            self._xy = [0, 0]
        else:
            self._xy = None

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self._brightness

    @property
    def rgb_color(self):
        """ RGB color value. """
        return self._rgb

    @property
    def color_xy(self):
        """ RGB color value. """
        return self._xy

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

        if ATTR_RGB_COLOR in kwargs and \
           self._topic["rgb_command_topic"] is not None:
            self._rgb = kwargs[ATTR_RGB_COLOR]
            rgb = DEFAULT_RGB_PATTERN % tuple(self._rgb)
            mqtt.publish(self._hass, self._topic["rgb_command_topic"],
                         rgb, self._qos)

        if ATTR_BRIGHTNESS in kwargs and \
           self._topic["brightness_command_topic"] is not None:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            mqtt.publish(self._hass, self._topic["brightness_command_topic"],
                         self._brightness, self._qos)

        mqtt.publish(self._hass, self._topic["command_topic"],
                     self._payload["on"], self._qos)

        if self._optimistic:
            # optimistically assume that switch has changed state
            self._state = True
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        mqtt.publish(self._hass, self._topic["command_topic"],
                     self._payload["off"], self._qos)

        if self._optimistic:
            # optimistically assume that switch has changed state
            self._state = False
            self.update_ha_state()
