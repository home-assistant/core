"""Support for Notion binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import (
    BINARY_SENSOR_TYPES, SENSOR_BATTERY, SENSOR_DOOR, SENSOR_GARAGE_DOOR,
    SENSOR_LEAK, SENSOR_MISSING, SENSOR_SAFE, SENSOR_SLIDING, SENSOR_SMOKE_CO,
    SENSOR_WINDOW_HINGED_HORIZONTAL, SENSOR_WINDOW_HINGED_VERTICAL,
    NotionEntity)

from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Notion sensors based on a config entry."""
    notion = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for task in notion.tasks:
        if task['task_type'] not in BINARY_SENSOR_TYPES:
            continue

        name, device_class = BINARY_SENSOR_TYPES[task['task_type']]
        sensor = next(
            (s for s in notion.sensors if s['id'] == task['sensor_id'])
        )
        bridge = next(
            (b for b in notion.bridges if b['id'] == sensor['bridge']['id'])
        )
        system = next(
            (s for s in notion.systems if s['id'] == sensor['system_id'])
        )

        sensor_list.append(
            NotionBinarySensor(
                notion, task, sensor, bridge, system, name, device_class))

    async_add_entities(sensor_list, True)


class NotionBinarySensor(NotionEntity, BinarySensorDevice):
    """Define a Notion sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch new state data for the sensor."""
        new_data = next(
            (t for t in self._notion.tasks if t['id'] == self._task['id'])
        )

        if self._task['task_type'] == SENSOR_BATTERY:
            self._state = new_data['status']['value'] != 'battery_good'
        elif self._task['task_type'] == SENSOR_DOOR:
            self._state = new_data['status']['value'] != 'closed'
        elif self._task['task_type'] == SENSOR_GARAGE_DOOR:
            self._state = new_data['status']['value'] != 'closed'
        elif self._task['task_type'] == SENSOR_LEAK:
            self._state = new_data['status']['value'] != 'no_leak'
        elif self._task['task_type'] == SENSOR_MISSING:
            self._state = new_data['status']['value'] != 'not_missing'
        elif self._task['task_type'] == SENSOR_SAFE:
            self._state = new_data['status']['value'] != 'closed'
        elif self._task['task_type'] == SENSOR_SLIDING:
            self._state = new_data['status']['value'] != 'closed'
        elif self._task['task_type'] == SENSOR_SMOKE_CO:
            self._state = new_data['status']['value'] != 'no_alarm'
        elif self._task['task_type'] == SENSOR_WINDOW_HINGED_HORIZONTAL:
            self._state = new_data['status']['value'] != 'closed'
        elif self._task['task_type'] == SENSOR_WINDOW_HINGED_VERTICAL:
            self._state = new_data['status']['value'] != 'closed'
        else:
            _LOGGER.error(
                'Unknown binary sensory type: %s', self._task['task_type'])
