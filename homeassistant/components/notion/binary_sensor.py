"""Support for Notion binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback

from . import (
    BINARY_SENSOR_TYPES,
    SENSOR_BATTERY,
    SENSOR_DOOR,
    SENSOR_GARAGE_DOOR,
    SENSOR_LEAK,
    SENSOR_MISSING,
    SENSOR_SAFE,
    SENSOR_SLIDING,
    SENSOR_SMOKE_CO,
    SENSOR_WINDOW_HINGED_HORIZONTAL,
    SENSOR_WINDOW_HINGED_VERTICAL,
    NotionEntity,
)
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Notion sensors based on a config entry."""
    notion = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for task_id, task in notion.tasks.items():
        if task["task_type"] not in BINARY_SENSOR_TYPES:
            continue

        name, device_class = BINARY_SENSOR_TYPES[task["task_type"]]
        sensor = notion.sensors[task["sensor_id"]]

        sensor_list.append(
            NotionBinarySensor(
                notion,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                name,
                device_class,
            )
        )

    async_add_entities(sensor_list, True)


class NotionBinarySensor(NotionEntity, BinarySensorDevice):
    """Define a Notion sensor."""

    @property
    def is_on(self):
        """Return whether the sensor is on or off."""
        task = self._notion.tasks[self._task_id]

        if task["task_type"] == SENSOR_BATTERY:
            return self._state != "battery_good"
        if task["task_type"] in (
            SENSOR_DOOR,
            SENSOR_GARAGE_DOOR,
            SENSOR_SAFE,
            SENSOR_SLIDING,
            SENSOR_WINDOW_HINGED_HORIZONTAL,
            SENSOR_WINDOW_HINGED_VERTICAL,
        ):
            return self._state != "closed"
        if task["task_type"] == SENSOR_LEAK:
            return self._state != "no_leak"
        if task["task_type"] == SENSOR_MISSING:
            return self._state == "not_missing"
        if task["task_type"] == SENSOR_SMOKE_CO:
            return self._state != "no_alarm"

    @callback
    def update_from_latest_data(self):
        """Fetch new state data for the sensor."""
        task = self._notion.tasks[self._task_id]

        self._state = task["status"]["value"]
