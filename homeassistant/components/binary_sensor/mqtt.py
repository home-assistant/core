"""
Support for MQTT binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mqtt/
"""
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.components.binary_sensor import (BinarySensorDevice,
                                                    SENSOR_CLASSES)
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MQTT Binary sensor'
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'

DEPENDENCIES = ['mqtt']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add MQTT binary sensor."""
    if config.get('state_topic') is None:
        _LOGGER.error('Missing required variable: state_topic')
        return False

    sensor_class = config.get('sensor_class')
    if sensor_class not in SENSOR_CLASSES:
        _LOGGER.warning('Unknown sensor class: %s', sensor_class)
        sensor_class = None

    add_devices([MqttBinarySensor(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic', None),
        sensor_class,
        config.get('qos', DEFAULT_QOS),
        config.get('payload_on', DEFAULT_PAYLOAD_ON),
        config.get('payload_off', DEFAULT_PAYLOAD_OFF),
        config.get(CONF_VALUE_TEMPLATE))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttBinarySensor(BinarySensorDevice):
    """Representation a binary sensor that is updated by MQTT."""

    def __init__(self, hass, name, state_topic, sensor_class, qos, payload_on,
                 payload_off, value_template):
        """Initialize the MQTT binary sensor."""
        self._hass = hass
        self._name = name
        self._state = False
        self._state_topic = state_topic
        self._sensor_class = sensor_class
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._qos = qos

        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
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
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def sensor_class(self):
        """Return the class of this sensor."""
        return self._sensor_class
