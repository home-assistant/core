"""
Sensor support for Wirelss Sensor Tags platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.wirelesstag/
"""

import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS)
from homeassistant.components.wirelesstag import (
    DEFAULT_ENTITY_NAMESPACE, DOMAIN as WIRELESSTAG_DOMAIN,
    WIRELESSTAG_TYPE_13BIT, WIRELESSTAG_TYPE_WATER,
    WIRELESSTAG_TYPE_ALSPRO,
    WirelessTagBaseSensor)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import TEMP_CELSIUS

DEPENDENCIES = ['wirelesstag']

_LOGGER = logging.getLogger(__name__)

SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'
SENSOR_MOISTURE = 'moisture'
SENSOR_LIGHT = 'light'

SENSOR_TEMPERATURE_F_ICON = 'temperature-fahrenheit'

SENSOR_TYPES = {
    SENSOR_TEMPERATURE: {
        'unit': TEMP_CELSIUS,
        'icon': 'temperature-celsius',
        'attr': 'temperature'
    },
    SENSOR_HUMIDITY: {
        'unit': '%',
        'icon': 'water-percent',
        'attr': 'humidity'
    },
    SENSOR_MOISTURE: {
        'unit': '%',
        'icon': 'water',
        'attr': 'moisture'
    },
    SENSOR_LIGHT: {
        'unit': 'lx',
        'icon': 'brightness-6',
        'attr': 'light'
    }
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    platform = hass.data.get(WIRELESSTAG_DOMAIN)
    sensors = []
    tags = platform.tags
    for _, tag in tags.items():
        for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
            if sensor_type in WirelessTagSensor.allowed_sensors(tag):
                sensors.append(WirelessTagSensor(
                    platform, tag, sensor_type, hass.config))

    add_devices(sensors, True)


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
                SENSOR_LIGHT]
        }

        tag_type = tag.tag_type
        return (
            sensors_per_tag_type[tag_type] if tag_type in sensors_per_tag_type
            else all_sensors)

    def __init__(self, api, tag, sensor_type, config):
        """Constructor with platform(api), tag and hass sensor type."""
        super().__init__(api, tag)

        self._sensor_type = sensor_type
        self._tag_attr = SENSOR_TYPES[self._sensor_type]['attr']
        self._unit_of_measurement = SENSOR_TYPES[self._sensor_type]['unit']
        self._icon = 'mdi:{}'.format(SENSOR_TYPES[self._sensor_type]['icon'])
        if sensor_type == SENSOR_TEMPERATURE and not config.units.is_metric:
            self._icon = 'mdi:{}'.format(SENSOR_TEMPERATURE_F_ICON)
        self.define_name(self._tag.name)

        # sensor.wirelesstag_bedroom_temperature
        self._entity_id = '{}.{}_{}_{}'.format('sensor', WIRELESSTAG_DOMAIN,
                                               self.underscored_name,
                                               self._sensor_type)
        self._state = self.updated_state_value()
        self._api.register_entity(self)

    @property
    def entity_id(self):
        """Ovverriden version."""
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
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def principal_value(self):
        """Return sensor current value."""
        return getattr(self._tag, self._tag_attr, False)

    def update_tag_info(self, event):
        """Handle push notification sent by tag manager."""
        new_value = self.principal_value
        try:
            if self._sensor_type == SENSOR_TEMPERATURE:
                new_value = event.data.get('temp')
            elif (self._sensor_type == SENSOR_HUMIDITY or
                  self._sensor_type == SENSOR_MOISTURE):
                new_value = event.data.get('cap')
            elif self._sensor_type == SENSOR_LIGHT:
                new_value = event.data.get('lux')
        except Exception as error:  # pylint: disable=W0703
            _LOGGER.info("Unable to update value of entity: \
                        %s error: %s event: %s", self, error, event)

        self._state = self.decorate_value(new_value)
        self.async_schedule_update_ha_state()
