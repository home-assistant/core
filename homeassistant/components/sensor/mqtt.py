"""
Support for MQTT sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt/
"""
import logging

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, STATE_UNKNOWN
from homeassistant.components.mqtt import CONF_STATE_TOPIC, CONF_QOS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_UNIT_OF_MEASUREMENT = 'unit_of_measurement'

DEFAULT_NAME = "MQTT Sensor"

PLATFORM_SCHEMA = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup MQTT Sensor."""
    add_devices_callback([MqttSensor(
        hass,
        config[CONF_NAME],
        config[CONF_STATE_TOPIC],
        config[CONF_QOS],
        config.get(CONF_UNIT_OF_MEASUREMENT),
        config.get(CONF_VALUE_TEMPLATE),
    )])


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
