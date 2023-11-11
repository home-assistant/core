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

from .const import DOMAIN

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

# ASSIGNMENT_ID = "id"
# ASSIGNMENT_NAME = "name"
# COURSE_ID = "course_id"
# ASSIGNMENT_DUE = "due_at"
# ASSIGNMENT_LINK = "html_url"

@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required Canvas base description keys."""
    value_fn: Callable[[dict[str, Any]], StateType]
    name_fn: Callable[[dict[str, Any]], StateType]

@dataclass
class BaseEntityDescription(SensorEntityDescription):
    """Describe Canvas sensor entity default overrides"""
    attr_fn: Callable[[dict[str, Any]], Mapping[str, Any] | None] = lambda data: None


@dataclass
class CanvasSensorEntityDescription(BaseEntityDescription, BaseEntityDescriptionMixin):
    """Describe Canvas resource sensor entity"""
    icon: str = "mdi:note-outline"


assignment_sensor_entity_description = CanvasSensorEntityDescription(
    key="upcoming_assignments",
    translation_key="upcoming_assignments",
    #device_class=SensorDeviceClass.ENUM，
    #options=["Assignment"]
    #native_unit_of_measurement="Assignment",
    #entity_category=EntityCategory.DIAGNOSTIC,
    #state_class=SensorStateClass.MEASUREMENT,
    name_fn=lambda data: str(data["course_id"]) + "-" + data["name"],
    value_fn=lambda data: data["due_at"],
    attr_fn=lambda data: {
        "Link": data["html_url"]
    }
)


def create_assignment_sensors(assignment_info):
    sensors = []
    for assignment in assignment_info:
        sensors.append(
            AssignmentSensorEntity(assignment_sensor_entity_description, assignment)
        )
    return sensors

class AssignmentSensorEntity(SensorEntity):
    """Defines an assignment sensor entity."""
    _attr_attribution = "Data provided by Canvas API"
    entity_description: CanvasSensorEntityDescription
    
    def __init__(
        self,
        entity_description: CanvasSensorEntityDescription,
        assignment_info
    ) -> None:
        """Initialize the assignment sensor."""
        self.entity_description = entity_description
        self.assignment_info = assignment_info
        self._attr_unique_id = f"{self.entity_description.key}_{self.assignment_info['course_id']}_{self.assignment_info['id']}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "Upcoming Assignments")},
            name="Upcoming Assignments",
            manufacturer="Canvas",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.entity_description.name_fn(self.assignment_info)

    @property
    def native_value(self):
        """Return the due time."""
        return self.entity_description.value_fn(self.assignment_info)
    
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self.entity_description.attr_fn(self.assignment_info)
    
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""
    assignment_sensors = create_assignment_sensors(assignment_info)
    async_add_entities(assignment_sensors)
