"""
homeassistant.components.light.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT light.

config for RGB Version with brightness:

light:
  platform: mqtt
  name: "Office Light RGB"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  brightness_state_topic: "office/rgb1/brightness/status"
  brightness_command_topic: "office/rgb1/brightness/set"
  rgb_state_topic: "office/rgb1/rgb/status"
  rgb_command_topic: "office/rgb1/rgb/set"
  qos: 0
  payload_on: "on"
  payload_off: "off"

config without RGB:

light:
  platform: mqtt
  name: "Office Light"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  qos: 0
  payload_on: "on"
  payload_off: "off"

"""
import logging
import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (Light,
                                            ATTR_BRIGHTNESS, ATTR_RGB_COLOR)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Light"
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_ON = "on"
DEFAULT_PAYLOAD_OFF = "off"
DEFAULT_RGB = [255, 255, 255]
DEFAULT_RGB_PATTERN = "%d,%d,%d"
DEFAULT_BRIGHTNESS = 120
DEFAULT_OPTIMISTIC = False

DEPENDENCIES = ['mqtt']

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Light. """

    if config.get('command_topic') is None:
        _LOGGER.error("Missing required variable: command_topic")
        return False

    if config.get('rgb_command_topic') is not None:
        add_devices_callback([MqttLightRGB(
            hass,
            config.get('name', DEFAULT_NAME),
            {"state_topic": config.get('state_topic'),
             "command_topic": config.get('command_topic'),
             "brightness_state_topic": config.get('brightness_state_topic'),
             "brightness_command_topic":
             config.get('brightness_command_topic'),
             "rgb_state_topic": config.get('rgb_state_topic'),
             "rgb_command_topic": config.get('rgb_command_topic')},
            config.get('rgb', DEFAULT_RGB),
            config.get('qos', DEFAULT_QOS),
            {"on": config.get('payload_on', DEFAULT_PAYLOAD_ON),
             "off": config.get('payload_off', DEFAULT_PAYLOAD_OFF)},
            config.get('brightness', DEFAULT_BRIGHTNESS),
            config.get('optimistic', DEFAULT_OPTIMISTIC))])

    else:
        add_devices_callback([MqttLight(
            hass,
            config.get('name', DEFAULT_NAME),
            {"state_topic": config.get('state_topic'),
             "command_topic": config.get('command_topic')},
            config.get('qos', DEFAULT_QOS),
            {"on": config.get('payload_on', DEFAULT_PAYLOAD_ON),
             "off": config.get('payload_off', DEFAULT_PAYLOAD_OFF)},
            config.get('optimistic', DEFAULT_OPTIMISTIC))])


class MqttLight(Light):
    """ Provides a demo light. """

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name,
                 topic,
                 qos,
                 payload,
                 optimistic):

        self._hass = hass
        self._name = name
        self._topic = topic
        self._qos = qos
        self._payload = payload
        self._optimistic = optimistic
        self._state = False

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
            # subscribe the state_topic
            mqtt.subscribe(self._hass, self._topic["state_topic"],
                           message_received, self._qos)

    @property
    def should_poll(self):
        """ No polling needed for a demo light. """
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


class MqttLightRGB(MqttLight):
    """ Provides a demo RGB light. """

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name,
                 topic,
                 rgb, qos,
                 payload,
                 brightness, optimistic):

        super().__init__(hass, name, topic, qos,
                         payload, optimistic)

        self._rgb = rgb
        self._brightness = brightness
        self._xy = [[0.5, 0.5]]

        def brightness_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            self._brightness = int(payload)
            self.update_ha_state()

        def rgb_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            self._rgb = [int(val) for val in payload.split(',')]
            self.update_ha_state()

        if self._topic["brightness_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["brightness_state_topic"],
                           brightness_received, self._qos)

        if self._topic["rgb_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["rgb_state_topic"],
                           rgb_received, self._qos)

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
