"""Sensor platform for the Instructure-Canvas integration"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN

from .canvas_api import CanvasAPI


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required Canvas base description keys."""
    value_fn: Callable[[dict[str, Any]], StateType]
    name_fn: Callable[[dict[str, Any]], StateType]

@dataclass
class BaseEntityDescription(SensorEntityDescription):
    """Describe Canvas sensor entity default overrides"""

    icon: str = "mdi:school"
    attr_fn: Callable[[dict[str, Any]], Mapping[str, Any] | None] = lambda data: None
    avabl_fn: Callable[[dict[str, Any]], bool] = lambda data: True


@dataclass
class CanvasSensorEntityDescription(BaseEntityDescription, BaseEntityDescriptionMixin):
    """Describe Canvas resource sensor entity"""
    fetch_data: Callable = None


SENSOR_DESCRIPTIONS: tuple[CanvasSensorEntityDescription, ...] = (
    CanvasSensorEntityDescription(
        key="upcoming_assignments",
        translation_key="upcoming_assignments",
        icon="mdi:note-outline",
        avabl_fn=lambda data: len(data) > 0,
        name_fn=lambda _: "Assignments",
        value_fn= lambda data: datetime_process(data[0]["due_at"]),
        attr_fn=lambda data: {
            'assignments': [{
                'title': assignment['name'],
                'description': assignment['description'],
                'due_at': assignment['due_at'],
            } for assignment in data]
        },
        fetch_data=lambda api, course_id: api.async_get_assignments(course_id),
    ),
    CanvasSensorEntityDescription(
        key="announcements",
        translation_key="announcements",
        icon="mdi:message-alert",
        avabl_fn=lambda data: len(data) > 0,
        name_fn=lambda _: "Announcements",
        value_fn= lambda data: data[0]["title"][:20],
        attr_fn=lambda data: {
            'messages': [{
                'title': announcement['title'],
                'date': announcement['posted_at'],
                'author': announcement['user_name'],
            } for announcement in data]
        },
        fetch_data=lambda api, course_id: api.async_get_announcements(course_id),
    ),
)

inbox_sensor_entity_description = CanvasSensorEntityDescription(
    key="inbox",
    translation_key="inbox",
    icon="mdi:email",
    avabl_fn=lambda data: len(data) > 0,
    name_fn=lambda _: "Inbox",
    value_fn= lambda data: data[0]["subject"][:20],
    attr_fn=lambda data: {
        'messages': [{
            'title': message['subject'],
            'date': message['last_message_at'],
            'author': message['participants'][0]['full_name'],
        } for message in data]
    },
    fetch_data=lambda api, _: api.async_get_conversations(),
)

def datetime_process(date_time):
    standard_timestamp = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    pretty_time = standard_timestamp.strftime("%d %b %H:%M")
    return pretty_time


class CanvasSensorEntity(SensorEntity):
    """Defines a Canvas sensor entity."""
    _attr_attribution = "Data provided by Canvas API"
    data: dict[str, Any] | None = None
    entity_description: CanvasSensorEntityDescription

    def __init__(
        self,
        api: CanvasAPI,
        entity_description: CanvasSensorEntityDescription,
        course_name: str,
        course_id: int,
    ) -> None:
        """Initialize a Canvas sensor."""
        self.api = api
        self.entity_description = entity_description
        self.course_name = course_name
        self.course_id = course_id
        self._attr_unique_id = f"{self.course_id}-{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.entity_description.key)},
            name=self.course_name,
            manufacturer="Canvas",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self):
        # TODO: Add try-catch
        self.data = await self.entity_description.fetch_data(self.api, self.course_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        if not self.available:
            return None

        return f"{self.course_name} - {self.entity_description.name_fn(self.data)}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.data is not None
            and self.entity_description.avabl_fn(self.data)
        )

    @property
    def native_value(self):
        """Return the due time."""
        if not self.available:
            return None

        return self.entity_description.value_fn(self.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra state attributes."""
        return self.entity_description.attr_fn(self.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""

    api = hass.data[DOMAIN][entry.entry_id]
    courses = entry.options["courses"] # k: course name, v: course id

    entities = [CanvasSensorEntity(api, description, course_name, courses[course_name])
            for description in SENSOR_DESCRIPTIONS
            for course_name in courses]

    entities.append(CanvasSensorEntity(api, inbox_sensor_entity_description, "", ""))

    async_add_entities(
        tuple(entities),
        update_before_add = True
    )

