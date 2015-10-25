"""
homeassistant.components.light.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT light.
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

DEFAULT_STATE_TOPIC = "homeassistant/light/state"
DEFAULT_COMMAND_TOPIC = "homeassistant/light/switch"

DEFAULT_STATE_BRIGHTNESS = "homeassistant/light/brightness/state"
DEFAULT_COMMAND_BRIGHTNESS = "homeassistant/light/brightness/set"

DEFAULT_STATE_RGB = "homeassistant/light/rgb/state"
DEFAULT_COMMAND_RGB = "homeassistant/light/rgb/set"

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
        config.get('state_topic', DEFAULT_STATE_TOPIC),
        config.get('command_topic', DEFAULT_COMMAND_TOPIC),
        config.get('brightness_state_topic', DEFAULT_STATE_BRIGHTNESS),
        config.get('brightness_command_topic', DEFAULT_COMMAND_BRIGHTNESS),
        config.get('rgb_state_topic', DEFAULT_STATE_RGB),
        config.get('rgb_command_topic', DEFAULT_COMMAND_RGB),
        config.get('rgb', DEFAULT_RGB),
        config.get('qos', DEFAULT_QOS),
        config.get('payload_on', DEFAULT_PAYLOAD_ON),
        config.get('payload_off', DEFAULT_PAYLOAD_OFF),
        config.get('brightness', DEFAULT_BRIGHTNESS))])


class MqttLight(Light):
    """ Provides a demo switch. """

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments,too-many-locals,bad-builtin
    # Eight is reasonable in this case.

    def __init__(self, hass, name,
                 state_topic, command_topic,
                 brightness_state_topic, brightness_command_topic,
                 rgb_state_topic, rgb_command_topic,
                 rgb, qos,
                 payload_on, payload_off,
                 brightness):

        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._brightness_state_topic = brightness_state_topic
        self._brightness_command_topic = brightness_command_topic
        self._rgb_state_topic = rgb_state_topic
        self._rgb_command_topic = rgb_command_topic
        self._rgb = rgb
        self._qos = qos
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._brightness = brightness
        self._xy = [[0.5, 0.5]]
        self._state = False

        def message_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            if payload == self._payload_on:
                self._state = True
                self.update_ha_state()
            elif payload == self._payload_off:
                self._state = False
                self.update_ha_state()

        def brightness_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            self._brightness = int(payload)
            self.update_ha_state()

        def rgb_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            rgb = payload.split(",")
            self._rgb = list(map(int, rgb))
            self.update_ha_state()

        # subscribe the state_topic
        mqtt.subscribe(self._hass, self._state_topic,
                       message_received, self._qos)
        mqtt.subscribe(self._hass, self._brightness_state_topic,
                       brightness_received, self._qos)
        mqtt.subscribe(self._hass, self._rgb_state_topic,
                       rgb_received, self._qos)

    @property
    def should_poll(self):
        """ No polling needed for a demo light. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

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
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """

        if ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]
            rgb = DEFAULT_RGB_PATTERN % tuple(self._rgb)
            mqtt.publish(self._hass, self._rgb_command_topic, rgb, self._qos)

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            mqtt.publish(self._hass, self._brightness_command_topic,
                         self._brightness, self._qos)

        if not self._state:
            self._state = True
            mqtt.publish(self._hass, self._command_topic,
                         self._payload_on, self._qos)
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = False
        mqtt.publish(self._hass, self._command_topic,
                     self._payload_off, self._qos)
        self.update_ha_state()
