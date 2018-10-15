"""
Support for AquaLogic sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.aqualogic/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_MONITORED_CONDITIONS,
                                 TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
import homeassistant.components.aqualogic as aq
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['aqualogic']

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = ['%', '%']
SALT_UNITS = ['g/L', 'PPM']
WATT_UNITS = ['W', 'W']
NO_UNITS = [None, None]

# sensor_type [ description, unit, icon ]
# sensor_type corresponds to property names in aqualogic.core.AquaLogic
SENSOR_TYPES = {
    'air_temp': ['Air Temperature', TEMP_UNITS, 'mdi:thermometer'],
    'pool_temp': ['Pool Temperature', TEMP_UNITS, 'mdi:oil-temperature'],
    'spa_temp': ['Spa Temperature', TEMP_UNITS, 'mdi:oil-temperature'],
    'pool_chlorinator': ['Pool Chlorinator', PERCENT_UNITS, 'mdi:gauge'],
    'spa_chlorinator': ['Spa Chlorinator', PERCENT_UNITS, 'mdi:gauge'],
    'salt_level': ['Salt Level', SALT_UNITS, 'mdi:gauge'],
    'pump_speed': ['Pump Speed', PERCENT_UNITS, 'mdi:speedometer'],
    'pump_power': ['Pump Power', WATT_UNITS, 'mdi:gauge'],
    'status': ['Status', NO_UNITS, 'mdi:alert']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the sensor platform."""
    sensors = []

    processor = hass.data[aq.DOMAIN]
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        sensors.append(AquaLogicSensor(processor, sensor_type))

    async_add_entities(sensors)


class AquaLogicSensor(Entity):
    """Sensor implementation for the AquaLogic component."""

    def __init__(self, processor, sensor_type):
        """Initialize sensor."""
        self._processor = processor
        self._type = sensor_type
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return "AquaLogic {}".format(SENSOR_TYPES[self._type][0])

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        panel = self._processor.panel
        if panel is None:
            return None
        if panel.is_metric:
            return SENSOR_TYPES[self._type][1][0]
        return SENSOR_TYPES[self._type][1][1]

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self._type][2]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            aq.UPDATE_TOPIC, self.async_update_callback)

    @callback
    def async_update_callback(self):
        """Update callback."""
        panel = self._processor.panel
        if panel is not None:
            self._state = getattr(panel, self._type)
            self.async_schedule_update_ha_state()
