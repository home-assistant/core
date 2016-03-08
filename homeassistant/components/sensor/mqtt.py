"""
Support for MQTT sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt/
"""
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.const import CONF_VALUE_TEMPLATE, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Sensor"
DEFAULT_QOS = 0

DEPENDENCIES = ['mqtt']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup MQTT Sensor."""
    if config.get('state_topic') is None:
        _LOGGER.error("Missing required variable: state_topic")
        return False

    add_devices_callback([MqttSensor(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic'),
        config.get('qos', DEFAULT_QOS),
        config.get('unit_of_measurement'),
        config.get(CONF_VALUE_TEMPLATE))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttSensor(Entity):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, hass, name, state_topic, qos, unit_of_measurement,
                 value_template):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._qos = qos
        self._unit_of_measurement = unit_of_measurement

        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            if value_template is not None:
                payload = template.render_with_possible_json_value(
                    hass, value_template, payload)
            self._state = payload
            self.update_ha_state()

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state
