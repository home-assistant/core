"""
Sensor support for Wireless Sensor Tags platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.wirelesstag/
"""

import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS)
from homeassistant.components.wirelesstag import (
    DOMAIN as WIRELESSTAG_DOMAIN,
    WIRELESSTAG_TYPE_13BIT, WIRELESSTAG_TYPE_WATER,
    WIRELESSTAG_TYPE_ALSPRO,
    WIRELESSTAG_TYPE_WEMO_DEVICE,
    SIGNAL_TAG_UPDATE,
    WirelessTagBaseSensor)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import TEMP_CELSIUS

DEPENDENCIES = ['wirelesstag']

_LOGGER = logging.getLogger(__name__)

SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'
SENSOR_MOISTURE = 'moisture'
SENSOR_LIGHT = 'light'

SENSOR_TYPES = {
    SENSOR_TEMPERATURE: {
        'unit': TEMP_CELSIUS,
        'attr': 'temperature'
    },
    SENSOR_HUMIDITY: {
        'unit': '%',
        'attr': 'humidity'
    },
    SENSOR_MOISTURE: {
        'unit': '%',
        'attr': 'moisture'
    },
    SENSOR_LIGHT: {
        'unit': 'lux',
        'attr': 'light'
    }
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    platform = hass.data.get(WIRELESSTAG_DOMAIN)
    sensors = []
    tags = platform.tags
    for tag in tags.values():
        for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
            if sensor_type in WirelessTagSensor.allowed_sensors(tag):
                sensors.append(WirelessTagSensor(
                    platform, tag, sensor_type, hass.config))

    add_entities(sensors, True)


class WirelessTagSensor(WirelessTagBaseSensor):
    """Representation of a Sensor."""

    @classmethod
    def allowed_sensors(cls, tag):
        """Return array of allowed sensor types for tag."""
        all_sensors = SENSOR_TYPES.keys()
        sensors_per_tag_type = {
            WIRELESSTAG_TYPE_13BIT: [
                SENSOR_TEMPERATURE,
                SENSOR_HUMIDITY],
            WIRELESSTAG_TYPE_WATER: [
                SENSOR_TEMPERATURE,
                SENSOR_MOISTURE],
            WIRELESSTAG_TYPE_ALSPRO: [
                SENSOR_TEMPERATURE,
                SENSOR_HUMIDITY,
                SENSOR_LIGHT],
            WIRELESSTAG_TYPE_WEMO_DEVICE: []
        }

        tag_type = tag.tag_type
        return (
            sensors_per_tag_type[tag_type] if tag_type in sensors_per_tag_type
            else all_sensors)

    def __init__(self, api, tag, sensor_type, config):
        """Initialize a WirelessTag sensor."""
        super().__init__(api, tag)

        self._sensor_type = sensor_type
        self._tag_attr = SENSOR_TYPES[self._sensor_type]['attr']
        self._unit_of_measurement = SENSOR_TYPES[self._sensor_type]['unit']
        self._name = self._tag.name

        # I want to see entity_id as:
        # sensor.wirelesstag_bedroom_temperature
        # and not as sensor.bedroom for temperature and
        # sensor.bedroom_2 for humidity
        self._entity_id = '{}.{}_{}_{}'.format('sensor', WIRELESSTAG_DOMAIN,
                                               self.underscored_name,
                                               self._sensor_type)

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass,
            SIGNAL_TAG_UPDATE.format(self.tag_id),
            self._update_tag_info_callback)

    @property
    def entity_id(self):
        """Overriden version."""
        return self._entity_id

    @property
    def underscored_name(self):
        """Provide name savvy to be used in entity_id name of self."""
        return self.name.lower().replace(" ", "_")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._sensor_type

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def principal_value(self):
        """Return sensor current value."""
        return getattr(self._tag, self._tag_attr, False)

    @callback
    def _update_tag_info_callback(self, event):
        """Handle push notification sent by tag manager."""
        if event.data.get('id') != self.tag_id:
            return

        _LOGGER.info("Entity to update state: %s event data: %s",
                     self, event.data)
        new_value = self.principal_value
        try:
            if self._sensor_type == SENSOR_TEMPERATURE:
                new_value = event.data.get('temp')
            elif (self._sensor_type == SENSOR_HUMIDITY or
                  self._sensor_type == SENSOR_MOISTURE):
                new_value = event.data.get('cap')
            elif self._sensor_type == SENSOR_LIGHT:
                new_value = event.data.get('lux')
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.info("Unable to update value of entity: \
                        %s error: %s event: %s", self, error, event)

        self._state = self.decorate_value(new_value)
        self.async_schedule_update_ha_state()
