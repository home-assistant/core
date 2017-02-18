"""
Sensor for monitoring plants with Xiaomi Mi Plant sensors
"""

#import logging
import voluptuous as vol
from homeassistant.const import (
    CONF_PLATFORM, CONF_NAME, STATE_UNKNOWN, CONF_UNIT_OF_MEASUREMENT, ATTR_BATTERY_LEVEL, TEMP_CELSIUS, ATTR_TEMPERATURE)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback

DEFAULT_NAME = 'MiGardener'
DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
})

ATTRIBUTES = (
    ('battery', ATTR_BATTERY_LEVEL, '%'),
    ('temperature', ATTR_TEMPERATURE, TEMP_CELSIUS),
    ('moisture', 'moisture', '%'),
    ('conductivity', 'conductivity', 'µS/cm'),
    ('brightness', 'brightness', 'lux'),
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up MQTT Sensor."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    for attrib in ATTRIBUTES:
        add_devices([MiGardener(
            hass,
            config.get(CONF_NAME),
            config.get(CONF_STATE_TOPIC),
            attrib[0],
            attrib[1],
            attrib[2],
        )])


class MiGardener(Entity):

    def __init__(self, hass, device_name, state_topic, mqtt_attrib_name, attrib_name, unit_of_measurement):
        self._state = STATE_UNKNOWN
        self.hass = hass
        self._name = '{} {}'.format(device_name, attrib_name)
        self._state_topic = '{}/{}'.format(state_topic,mqtt_attrib_name)
        self._unit_of_measurement = unit_of_measurement

        @callback
        def message_received(topic, payload, _):
            """A new MQTT message has been received."""
            self._state = payload
            hass.async_add_job(self.async_update_ha_state())

        mqtt.subscribe(hass, self._state_topic, message_received)

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
