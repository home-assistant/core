"""
Support for Minut Point.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.point/
"""
import logging

from homeassistant.components.point import (
    DOMAIN as PARENT_DOMAIN, MinutPointEntity)
from homeassistant.components.point.const import (
    DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_PRESSURE, DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.dt import parse_datetime

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_SOUND = 'sound_level'

SENSOR_TYPES = {
    DEVICE_CLASS_TEMPERATURE: (None, 1, TEMP_CELSIUS),
    DEVICE_CLASS_PRESSURE: (None, 0, 'hPa'),
    DEVICE_CLASS_HUMIDITY: (None, 1, '%'),
    DEVICE_CLASS_SOUND: ('mdi:ear-hearing', 1, 'dBa'),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Point's sensors based on a config entry."""
    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[POINT_DOMAIN][config_entry.entry_id]
        async_add_entities((MinutPointSensor(client, device_id, sensor_type)
                            for sensor_type in SENSOR_TYPES), True)

    async_dispatcher_connect(
        hass, POINT_DISCOVERY_NEW.format(PARENT_DOMAIN, POINT_DOMAIN),
        async_discover_sensor)


class MinutPointSensor(MinutPointEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, point_client, device_id, device_class):
        """Initialize the entity."""
        super().__init__(point_client, device_id, device_class)
        self._device_prop = SENSOR_TYPES[device_class]

    @callback
    def _update_callback(self):
        """Update the value of the sensor."""
        if self.is_updated:
            _LOGGER.debug('Update sensor value for %s', self)
            self._value = self.device.sensor(self.device_class)
            self._updated = parse_datetime(self.device.last_update)
            self.async_schedule_update_ha_state()

    @property
    def icon(self):
        """Return the icon representation."""
        return self._device_prop[0]

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self.value, self._device_prop[1])

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._device_prop[2]
