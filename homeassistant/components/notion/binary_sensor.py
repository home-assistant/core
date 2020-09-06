"""Support for Notion binary sensors."""
import logging
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from . import NotionEntity
from .const import (
    DATA_COORDINATOR,
    DOMAIN,
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
)

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_TYPES = {
    SENSOR_BATTERY: ("Low Battery", "battery"),
    SENSOR_DOOR: ("Door", "door"),
    SENSOR_GARAGE_DOOR: ("Garage Door", "garage_door"),
    SENSOR_LEAK: ("Leak Detector", "moisture"),
    SENSOR_MISSING: ("Missing", "connectivity"),
    SENSOR_SAFE: ("Safe", "door"),
    SENSOR_SLIDING: ("Sliding Door/Window", "door"),
    SENSOR_SMOKE_CO: ("Smoke/Carbon Monoxide Detector", "smoke"),
    SENSOR_WINDOW_HINGED_HORIZONTAL: ("Hinged Window", "window"),
    SENSOR_WINDOW_HINGED_VERTICAL: ("Hinged Window", "window"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    """Set up Notion sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

    sensor_list = []
    for task_id, task in coordinator.data["tasks"].items():
        if task["task_type"] not in BINARY_SENSOR_TYPES:
            continue

        name, device_class = BINARY_SENSOR_TYPES[task["task_type"]]
        sensor = coordinator.data["sensors"][task["sensor_id"]]

        sensor_list.append(
            NotionBinarySensor(
                coordinator,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                name,
                device_class,
            )
        )

    async_add_entities(sensor_list)


class NotionBinarySensor(NotionEntity, BinarySensorEntity):
    """Define a Notion sensor."""

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        self._state = self.coordinator.data["tasks"][self._task_id]["status"]["value"]

    @property
    def is_on(self) -> bool:
        """Return whether the sensor is on or off."""
        task = self.coordinator.data["tasks"][self._task_id]

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
