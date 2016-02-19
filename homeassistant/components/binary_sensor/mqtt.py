"""
homeassistant.components.binary_sensor.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mqtt/
"""
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.util import template

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MQTT Binary sensor'
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'

DEPENDENCIES = ['mqtt']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Add MQTT binary sensor. """

    if config.get('state_topic') is None:
        _LOGGER.error('Missing required variable: state_topic')
        return False

    add_devices([MqttBinarySensor(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic', None),
        config.get('qos', DEFAULT_QOS),
        config.get('payload_on', DEFAULT_PAYLOAD_ON),
        config.get('payload_off', DEFAULT_PAYLOAD_OFF),
        config.get(CONF_VALUE_TEMPLATE))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttBinarySensor(BinarySensorDevice):
    """ Represents a binary sensor that is updated by MQTT. """
    def __init__(self, hass, name, state_topic, qos, payload_on, payload_off,
                 value_template):
        self._hass = hass
        self._name = name
        self._state = False
        self._state_topic = state_topic
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._qos = qos

        def message_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            if value_template is not None:
                payload = template.render_with_possible_json_value(
                    hass, value_template, payload)
            if payload == self._payload_on:
                self._state = True
                self.update_ha_state()
            elif payload == self._payload_off:
                self._state = False
                self.update_ha_state()

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """ No polling needed. """
        return False

    @property
    def name(self):
        """ The name of the binary sensor. """
        return self._name

    @property
    def is_on(self):
        """ True if the binary sensor is on. """
        return self._state
