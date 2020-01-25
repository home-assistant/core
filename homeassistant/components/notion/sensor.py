"""Support for Notion sensors."""
import logging

from . import SENSOR_TEMPERATURE, SENSOR_TYPES, NotionEntity
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Notion sensors based on a config entry."""
    notion = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for task_id, task in notion.tasks.items():
        if task["task_type"] not in SENSOR_TYPES:
            continue

        name, device_class, unit = SENSOR_TYPES[task["task_type"]]
        sensor = notion.sensors[task["sensor_id"]]

        sensor_list.append(
            NotionSensor(
                notion,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                name,
                device_class,
                unit,
            )
        )

    async_add_entities(sensor_list, True)


class NotionSensor(NotionEntity):
    """Define a Notion sensor."""

    def __init__(
        self, notion, task_id, sensor_id, bridge_id, system_id, name, device_class, unit
    ):
        """Initialize the entity."""
        super().__init__(
            notion, task_id, sensor_id, bridge_id, system_id, name, device_class
        )

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
        task = self._notion.tasks[self._task_id]

        if task["task_type"] == SENSOR_TEMPERATURE:
            self._state = round(float(task["status"]["value"]), 1)
        else:
            _LOGGER.error(
                "Unknown task type: %s: %s",
                self._notion.sensors[self._sensor_id],
                task["task_type"],
            )
