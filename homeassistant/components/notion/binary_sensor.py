"""Support for Notion binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import (
    ATTR_BRIDGE_MODE, ATTR_BRIDGE_NAME, ATTR_SYSTEM_MODE, ATTR_SYSTEM_NAME,
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
    def is_on(self):
        """Return whether the sensor is on or off."""
        if self._task['task_type'] == SENSOR_BATTERY:
            return self._state != 'battery_good'
        if self._task['task_type'] in (
                SENSOR_DOOR, SENSOR_GARAGE_DOOR, SENSOR_SAFE, SENSOR_SLIDING,
                SENSOR_WINDOW_HINGED_HORIZONTAL,
                SENSOR_WINDOW_HINGED_VERTICAL):
            return self._state != 'closed'
        if self._task['task_type'] == SENSOR_LEAK:
            return self._state != 'no_leak'
        if self._task['task_type'] == SENSOR_MISSING:
            return self._state == 'not_missing'
        if self._task['task_type'] == SENSOR_SMOKE_CO:
            return self._state != 'no_alarm'

    async def async_update(self):
        """Fetch new state data for the sensor."""
        try:
            new_bridge_data = next(
                (b for b in self._notion.bridges
                 if b['id'] == self._bridge['id'])
            )
        except StopIteration:
            _LOGGER.error(
                'Bridge missing (was it removed?): %s: %s',
                self._sensor['name'], self._task['task_type'])

        try:
            new_system_data = next(
                (s for s in self._notion.systems
                 if s['id'] == self._system['id'])
            )
        except StopIteration:
            _LOGGER.error(
                'Task missing (was it removed?): %s: %s',
                self._sensor['name'], self._task['task_type'])

        try:
            new_task_data = next(
                (t for t in self._notion.tasks if t['id'] == self._task['id'])
            )
        except StopIteration:
            _LOGGER.error(
                'Task missing (was it removed?): %s: %s',
                self._sensor['name'], self._task['task_type'])
            return

        self._state = new_task_data['status']['value']
        self._attrs.update({
            ATTR_BRIDGE_MODE: new_bridge_data['mode'],
            ATTR_BRIDGE_NAME: new_bridge_data['name'],
            ATTR_SYSTEM_MODE: new_system_data['mode'],
            ATTR_SYSTEM_NAME: new_system_data['name'],
        })
