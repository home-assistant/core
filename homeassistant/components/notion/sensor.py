"""Support for Notion sensors."""
import logging

from . import (
    ATTR_BRIDGE_MODE, ATTR_BRIDGE_NAME, ATTR_SYSTEM_MODE, ATTR_SYSTEM_NAME,
    SENSOR_TEMPERATURE, SENSOR_TYPES, NotionEntity)
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Notion sensors based on a config entry."""
    notion = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for task in notion.tasks:
        if task['task_type'] not in SENSOR_TYPES:
            continue

        name, device_class, unit = SENSOR_TYPES[task['task_type']]
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
            NotionSensor(
                notion,
                task,
                sensor,
                bridge,
                system,
                name,
                device_class,
                unit
            ))

    async_add_entities(sensor_list, True)


class NotionSensor(NotionEntity):
    """Define a Notion sensor."""

    def __init__(
            self,
            notion,
            task,
            sensor,
            bridge,
            system,
            name,
            device_class,
            unit):
        """Initialize the entity."""
        super().__init__(
            notion, task, sensor, bridge, system, name, device_class)

        self._unit = unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

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

        if self._task['task_type'] == SENSOR_TEMPERATURE:
            self._state = round(float(new_task_data['status']['value']), 1)
        else:
            _LOGGER.error(
                'Unknown task type: %s: %s',
                self._sensor['name'], self._task['task_type'])
        self._attrs.update({
            ATTR_BRIDGE_MODE: new_bridge_data['mode'],
            ATTR_BRIDGE_NAME: new_bridge_data['name'],
            ATTR_SYSTEM_MODE: new_system_data['mode'],
            ATTR_SYSTEM_NAME: new_system_data['name'],
        })
