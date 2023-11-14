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

# Assignment data
# ASSIGNMENT_ID = "id"
# ASSIGNMENT_NAME = "name"
# COURSE_ID = "course_id"
# ASSIGNMENT_DUE = "due_at"
# ASSIGNMENT_LINK = "html_url"

# Conversation data
# MESSAGE_ID = "id"
# MESSAGE_DATE = "start_at"
# CONVERSATION_PARTICIPANTS = "participants"
# MESSAGE_SUBJECT = "subject"
# MSG_PREVIEW = "last_message"


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


SENSOR_DESCRIPTIONS: tuple[CanvasSensorEntityDescription, ...] = (
    CanvasSensorEntityDescription(
        key="upcoming_assignments",
        translation_key="upcoming_assignments",
        name_fn=lambda data: str(data["course_id"]) + "-" + data["name"],
        value_fn=lambda data: datetime_process(data["due_at"]),
        attr_fn=lambda data: {
            "Link": data["html_url"]
        }
    ),
    CanvasSensorEntityDescription(
        key="inbox",
        translation_key="inbox",
        name_fn=lambda data: ", ".join([p["full_name"] for p in data["participants"]]),
        value_fn=lambda data: {
            "Date": data["start_at"],
            "Subject": data["subject"],
            "Last message": data["last_message"]
        }
    )
)


def datetime_process(date_time):
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
    ) -> None:
        """Initialize a Canvas sensor."""
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.entity_description.key)},
            name="blabalbalab",
            manufacturer="Canvas",
            entry_type=DeviceEntryType.SERVICE,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""

    # use API to get some data

    data = None

    async_add_entities(
        (
            CanvasSensorEntity(description)
            for description in SENSOR_DESCRIPTIONS
        )
    )

