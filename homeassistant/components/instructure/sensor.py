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

from .const import DOMAIN, ANNOUNCMENTS_KEY, ASSIGNMENTS_KEY, CONVERSATIONS_KEY

from .coordinator import CanvasDataUpdateCoordinator


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required Canvas base description keys."""
    value_fn: Callable[[dict[str, Any]], StateType]
    name_fn: Callable[[dict[str, Any]], StateType]
    device_name: str


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


SENSOR_DESCRIPTIONS: {str: CanvasSensorEntityDescription} = {
    ASSIGNMENTS_KEY: CanvasSensorEntityDescription(
        device_name="Upcoming Assignments",
        key="temp1",
        translation_key="temp1",
        icon="mdi:note-outline",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data["name"],
        value_fn= lambda data: datetime_process(data["due_at"]),
        attr_fn=lambda data: {},
        fetch_data=lambda api, course_id: api.async_get_assignments(course_id),
    ),
    ANNOUNCMENTS_KEY: CanvasSensorEntityDescription(
        device_name="Announcements",
        key="temp2",
        translation_key="temp2",
        icon="mdi:message-alert",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data["title"],
        value_fn= lambda data: data["message"][:20],
        attr_fn=lambda data: {},
        fetch_data=lambda api, course_id: api.async_get_announcements(course_id),
    ),
    CONVERSATIONS_KEY: CanvasSensorEntityDescription(
        device_name="Inbox",
        key="temp2",
        translation_key="temp2",
        icon="mdi:email",
        avabl_fn=lambda data: data is not None,
        name_fn=lambda data: data["audience"],
        value_fn= lambda data: data["subject"][:20],
        attr_fn=lambda data: {},
        fetch_data=lambda api, _: api.async_get_conversations(),
    )
}


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
        entity_description: CanvasSensorEntityDescription,
        data: dict[str, Any],
        coordinator: CanvasDataUpdateCoordinator,
    ) -> None:
        """Initialize a Canvas sensor."""
        self.entity_description = entity_description
        self.data = data
        self.coordinator = coordinator 
        self._attr_unique_id = f"{self.entity_description.name_fn(self.data)}"

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

        return f"{self.entity_description.name_fn(self.data)}"

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

def reset_state(): # <- call this method on data update (or async_setup_entry, but probably more correct to call this)
    # deletes all old entities
    # ceates new ones

    # TODO: Basically do everything that 'async_setup_entry' does

    pass

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""

    reset_state()

    hass.data[DOMAIN][ASSIGNMENTS_KEY] = [
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

    hass.data[DOMAIN][ANNOUNCMENTS_KEY] = [
        {
            "title": "Hello!",
            "posted_at": "2023-10-30T21:59:59Z",
            "user_name": "[REDACTED]",
            "message": "Oh noooooooo"
        },
        {
            "title": "Hello again, my name is [REDACTED]! 😜",
            "posted_at": "2023-10-30T21:59:59Z",
            "user_name": "[REDACTED]",
            "message": "I am [REDACTED]"
        }
    ]

    hass.data[DOMAIN][CONVERSATIONS_KEY] = [
    {
        "id": 2424059,
        "subject": "",
        "workflow_state": "unread",
        "last_message": "Reminder that lecture tomorrow Tuesday 14/11 is cancelled due to illness. See you on Friday inste...",
        "last_message_at": "2023-11-13T21:40:39Z",
        "last_authored_message": None,
        "last_authored_message_at": None,
        "message_count": 1,
        "subscribed": True,
        "private": False,
        "starred": False,
        "properties": [],
        "audience": [
            1439
        ],
        "audience_contexts": {
            "courses": {
                "26488": [
                    "TeacherEnrollment"
                ]
            },
            "groups": {}
        },
        "avatar_url": "https://chalmers.instructure.com/images/messages/avatar-50.png",
        "participants": [
            {
                "id": 1439,
                "name": "Ulf Assarsson",
                "full_name": "Ulf Assarsson",
                "pronouns": None
            },
            {
                "id": 26768,
                "name": "Theo Wiik",
                "full_name": "Theo Wiik",
                "pronouns": None
            }
        ],
        "visible": True,
        "context_code": "course_26488",
        "context_name": "TDA362 / DIT224 Computer graphics"
    },
    ]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # TODO: turn into loop and handle missing data
    # note, I think its fixed with ".get(ASSIGNMENTS_KEY, [])", but needs to be tested /Tejo
    assignment_entities = [create_entity(ASSIGNMENTS_KEY, assignment, coordinator) for assignment in hass.data[DOMAIN].get(ASSIGNMENTS_KEY, [])]
    announcement_entities = [create_entity(ANNOUNCMENTS_KEY, announcement, coordinator) for announcement in hass.data[DOMAIN].get(ANNOUNCMENTS_KEY, [])]
    inbox_entities = [create_entity(CONVERSATIONS_KEY, conversation, coordinator) for conversation in hass.data[DOMAIN].get(CONVERSATIONS_KEY, [])]

    entities = assignment_entities + announcement_entities + inbox_entities

    async_add_entities(tuple(entities))


def create_entity(data_type: str, data: dict[str, Any], coordinator: CanvasDataUpdateCoordinator) -> CanvasSensorEntity:
    entity_description = SENSOR_DESCRIPTIONS[data_type]
    entity = CanvasSensorEntity(entity_description, data, coordinator)

    return entity
