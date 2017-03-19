"""
Support for MQTT sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.mqtt import CONF_STATE_TOPIC, CONF_QOS
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, STATE_UNKNOWN, CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv

import time
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

CONF_FORCE_UPDATE = 'force_update'
CONF_EXPIRE_AFTER = 'expire_after'

DEFAULT_NAME = 'MQTT Sensor'
DEFAULT_FORCE_UPDATE = False
DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
})

SCAN_INTERVAL = timedelta(seconds=1)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up MQTT Sensor."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    async_add_devices([MqttSensor(
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_UNIT_OF_MEASUREMENT),
        config.get(CONF_FORCE_UPDATE),
        config.get(CONF_EXPIRE_AFTER),
        value_template,
    )])


class MqttSensor(Entity):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, name, state_topic, qos, unit_of_measurement,
                 force_update, expire_after, value_template):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._name = name
        self._state_topic = state_topic
        self._qos = qos
        self._unit_of_measurement = unit_of_measurement
        self._force_update = force_update
        self._template = value_template
        self._expire_after = expire_after or 0
        self._value_expiration_at = 0

    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method must be run in the event loop and returns a coroutine.
        """
        @callback
        def message_received(topic, payload, qos):
            """ reset expiration time """
            self._value_expiration_at = time.time() + self._expire_after
            
            """A new MQTT message has been received."""
            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload, self._state)
            self._state = payload
            self.hass.async_add_job(self.async_update_ha_state())

        return mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """polling needed only for auto-expire"""
        return self._expire_after > 0
    
    def update(self):
        if self._expire_after > 0 and time.time() > self._value_expiration_at:
            self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state
