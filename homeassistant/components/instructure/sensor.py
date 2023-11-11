"""Sensor platform for the Instructure-Canvas integration"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntity,
    SensorEntityDescription,
)

from homeassistant.helpers.entity import Entity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.const import UnitOfTemperature

# Assignment info should be fetched via API
assignment_info = [
    {
    "id": 76160,
    "due_at": "2023-08-30T21:59:59Z",
    "course_id": 25271,
    "name": "First Assignment",
    "html_url": "https://chalmers.instructure.com/courses/25271/assignments/76160"
    },
    {
    "id": 76161,
    "due_at": "2023-09-30T21:59:59Z",
    "course_id": 25271,
    "name": "Second Assignment",
    "html_url": "https://chalmers.instructure.com/courses/25271/assignments/76160"
    },

    {
    "id": 76162,
    "due_at": "2023-10-30T21:59:59Z",
    "course_id": 25271,
    "name": "Third Assignment",
    "html_url": "https://chalmers.instructure.com/courses/25271/assignments/76160"
    }
]

ASSIGNMENT_ID = "id"
ASSIGNMENT_NAME = "name"
COURSE_ID = "course_id"
ASSIGNMENT_DUE = "due_at"
ASSIGNMENT_LINK = "html_url"


def create_assignment_sensors(assignment_info):
    sensors = []
    for assignment in assignment_info:
        sensors.append(
            AssignmentSensorEntity(
                assignment[ASSIGNMENT_ID],
                assignment[ASSIGNMENT_NAME],
                assignment[COURSE_ID],
                assignment[ASSIGNMENT_DUE],
                assignment[ASSIGNMENT_LINK],
            )
        )
    return sensors

class AssignmentSensorEntity(SensorEntity):
    """Defines an assignment sensor entity."""
    _attr_attribution = "Data provided by Canvas API"
    _attr_icon = "mdi:note-outline"

    def __init__(self, id, name, course_id, due, link) -> None:
        """Initialize the sensor."""
        self._id = id
        self._name = name
        self._course_id = course_id
        self._due = due
        self._link = link
    
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the due time."""
        return self._due
    
    # @property
    # def extra_state_attributes(self):
    #     """Return the state attributes."""
    #     return self._link
    
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""
    assignment_sensors = create_assignment_sensors(assignment_info)
    async_add_entities(assignment_sensors)
