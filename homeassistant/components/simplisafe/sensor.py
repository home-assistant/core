"""Support for SimpliSafe sensors."""
import logging

from simplipy.sensor import SensorTypes

from homeassistant.util.dt import utc_from_timestamp

from . import SENSOR_TYPE_LAST_EVENT, SENSOR_TYPES, SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_INFO = 'info'
ATTR_LAST_EVENT_TIMESTAMP = 'timestamp'
ATTR_SENSOR_NAME = 'sensor_serial'
ATTR_SENSOR_TYPE = 'sensor_type'


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensors = []
    for system in simplisafe.systems.values():
        for sensor_type in SENSOR_TYPES:
            name, icon = SENSOR_TYPES[sensor_type]
            sensors.append(
                SimpliSafeSensor(simplisafe, system, sensor_type, name, icon))

    async_add_entities(sensors)


class SimpliSafeSensor(SimpliSafeEntity):
    """Define a SimpliSafe sensor."""

    def __init__(self, simplisafe, system, sensor_type, name, icon):
        """Initialize."""
        super().__init__(system)
        self._entity_type = sensor_type
        self._icon = icon
        self._name = name
        self._simplisafe = simplisafe

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch new state data for the sensor."""
        if self._entity_type == SENSOR_TYPE_LAST_EVENT:
            data = self._simplisafe.last_event_data[self._system.system_id]

            self._state = data['eventId']
            self._attrs.update({
                ATTR_INFO: data['info'],
                ATTR_LAST_EVENT_TIMESTAMP: utc_from_timestamp(
                    data['eventTimestamp']),
                ATTR_SENSOR_NAME: data['sensorName'],
                ATTR_SENSOR_TYPE: SensorTypes(data['sensorType'])
            })
