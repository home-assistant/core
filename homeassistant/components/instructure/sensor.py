"""Sensor platform for the Instructure-Canvas integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    ANNOUNCEMENTS_KEY,
    ASSIGNMENTS_KEY,
    CONVERSATIONS_KEY,
    DOMAIN,
    GRADES_KEY,
    QUICK_LINKS_KEY,
)
from .coordinator import CanvasUpdateCoordinator

GLOBAL_UNIQUE_ID = 1


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required Canvas base description keys."""

    value_fn: Callable[[dict[str, Any]], StateType]
    name_fn: Callable[[dict[str, Any]], StateType]
    device_name: str


@dataclass
class BaseEntityDescription(SensorEntityDescription):
    """Describe Canvas sensor entity default overrides."""

    icon: str = "mdi:school"
    attr_fn: Callable[[dict[str, Any]], Mapping[str, Any] | None] = lambda data: None
    avabl_fn: Callable[[dict[str, Any]], bool] = lambda data: True


@dataclass
class CanvasSensorEntityDescription(BaseEntityDescription, BaseEntityDescriptionMixin):
    """Describe Canvas resource sensor entity."""


SENSOR_DESCRIPTIONS: {str: CanvasSensorEntityDescription} = {
    ASSIGNMENTS_KEY: CanvasSensorEntityDescription(
        device_name="Upcoming Assignments",
        key=ASSIGNMENTS_KEY,
        translation_key=ASSIGNMENTS_KEY,
        icon="mdi:note-outline",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data["name"] if data else "Default Assignment Name",
        value_fn=lambda data: datetime_process(data["due_at"])
        if data
        else "Default Due Date",
        attr_fn=lambda data, courses: {
            # "Course": courses[data["course_id"]],
            "Link": data["html_url"]
        }
        if data
        else {"Link": "Default Assignment Link"},
    ),
    ANNOUNCEMENTS_KEY: CanvasSensorEntityDescription(
        device_name="Announcements",
        key=ANNOUNCEMENTS_KEY,
        translation_key=ANNOUNCEMENTS_KEY,
        icon="mdi:message-alert",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data["title"] if data else "Default Announcement Title",
        value_fn=lambda data: data["read_state"] if data else "Default Read State",
        attr_fn=lambda data, courses: {
            # "Course": courses[data["context_code"].split("_")[1]],
            "Link": data["html_url"],
            "Post Time": datetime_process(data["posted_at"]),
        }
        if data
        else {"Link": "Default Link", "Post Time": "Default Post Time"},
    ),
    CONVERSATIONS_KEY: CanvasSensorEntityDescription(
        device_name="Inbox",
        key=CONVERSATIONS_KEY,
        translation_key=CONVERSATIONS_KEY,
        icon="mdi:email",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data["subject"] if data else "Default Inbox Subject",
        value_fn=lambda data: data["workflow_state"]
        if data
        else "Default Workflow State",
        attr_fn=lambda data, courses: {
            "Course": data["context_name"],
            "Initial Sender": data["participants"][0]["name"],
            "Last Message": data["last_message"],
            "Last Message Time": datetime_process(data["last_message_at"]),
        }
        if data
        else {
            "Course": "Default Course",
            "Initial Sender": "Default Sender",
            "Last Message": "Default Message",
            "Last Message Time": "Default Time",
        },
    ),
    GRADES_KEY: CanvasSensorEntityDescription(
        device_name="Grades",
        key=GRADES_KEY,
        translation_key=GRADES_KEY,
        icon="mdi:star",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data['assignment_name']
        if data
        else "Default Assignment",
        value_fn=lambda data: data["score"] if data else "Default Grade",
        attr_fn=lambda data, courses: {
            "Course Name": data["course_name"]
        }
        if data
        else {"Unknown Course"},
    ),
    QUICK_LINKS_KEY: CanvasSensorEntityDescription(
        device_name="Quick links",
        key=QUICK_LINKS_KEY,
        translation_key=QUICK_LINKS_KEY,
        icon="mdi:link",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data["name"],
        value_fn=lambda data: "",
        attr_fn=lambda data, courses: {
            "URL": data["url"],
        },
    ),
}


def datetime_process(date_time):
    if not date_time:
        return None
    standard_timestamp = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    pretty_time = standard_timestamp.strftime("%d %b %H:%M")
    return pretty_time


class CanvasSensorEntity(SensorEntity):
    """Defines a Canvas sensor entity."""

    _attr_attribution = "Data provided by Canvas API"
    entity_description: CanvasSensorEntityDescription

    def __init__(
        self,
        entity_description: CanvasSensorEntityDescription,
        unique_id: str,
        coordinator: CanvasUpdateCoordinator,
    ) -> None:
        """Initialize a Canvas sensor."""
        self.entity_description = entity_description
        self.coordinator = coordinator
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.entity_description.device_name)},
            name=self.entity_description.device_name,
            manufacturer="Canvas",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        if not self.available:
            return None

        return f"{self.entity_description.name_fn(self.get_data())}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.get_data() is not None
            and self.entity_description.avabl_fn(self.get_data())
        )

    @property
    def native_value(self):
        """Return the due time."""
        if not self.available:
            return None

        return self.entity_description.value_fn(self.get_data())

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra state attributes."""
        return self.entity_description.attr_fn(
            self.get_data(), self.coordinator.selected_courses
        )

    def get_data(self):
        return self.coordinator.data[self.entity_description.key][self._attr_unique_id]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    def update_entities(data_type: str, new_data: dict, curr_data: dict):
        """Add or remove sensor entities based on new data"""
        current_ids = set(curr_data.keys())
        new_ids = set(new_data.keys())

        to_add = new_ids - current_ids
        to_remove = current_ids - new_ids

        for entity_id in to_remove:
            entity = hass.data[DOMAIN][entry.entry_id]["entities"][data_type][entity_id]
            entity.async_remove(force_remove=True)

        new_entities = []

        for entity_id in to_add:
            description = SENSOR_DESCRIPTIONS[data_type]
            new_entity = CanvasSensorEntity(description, entity_id, coordinator)
            new_entities.append(new_entity)

            hass.data[DOMAIN][entry.entry_id]["entities"][data_type][
                entity_id
            ] = new_entity

        if new_entities:
            async_add_entities(tuple(new_entities))

    coordinator.update_entities = update_entities
    await coordinator.async_refresh()
