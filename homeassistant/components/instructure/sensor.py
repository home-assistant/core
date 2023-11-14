"""Sensor platform for the Instructure-Canvas integration"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass
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
    attr_fn: Callable[[dict[str, Any]], Mapping[str, Any] | None] = lambda data: None


@dataclass
class CanvasSensorEntityDescription(BaseEntityDescription, BaseEntityDescriptionMixin):
    """Describe Canvas resource sensor entity"""
    icon: str = "mdi:note-outline"
    fetch_data: Callable = None


SENSOR_DESCRIPTIONS: tuple[CanvasSensorEntityDescription, ...] = (
    CanvasSensorEntityDescription(
        key="upcoming_assignments",
        translation_key="upcoming_assignments",
        icon="mdi:school",
        name_fn=lambda data: data[0]["name"] if data else "No assignments in this course",
        value_fn= lambda data: datetime_process(data[0]["due_at"]) if data else "",
        attr_fn=lambda data: data,
        fetch_data=lambda api, course_id: api.async_get_assignments(course_id),
    ),
    CanvasSensorEntityDescription(
        key="inbox",
        translation_key="inbox",
        icon="mdi:email",
        name_fn=lambda data: data[0]["subject"] if data else "No messages in inbox",
        value_fn= lambda data: data[0]["last_message"] if data else "",
        attr_fn=lambda data: data,
        fetch_data=lambda api, course_id: api.async_get_conversations(course_id),
    )
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
        course_id: str,
    ) -> None:
        """Initialize a Canvas sensor."""
        self.api = api
        self.entity_description = entity_description
        self.course_id = course_id
        self._attr_unique_id = f"{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.entity_description.key)},
            name="blabalbalab",
            manufacturer="Canvas",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self):
        # TODO: Add try-catch
        self.data = await self.entity_description.fetch_data(self.api, self.course_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.entity_description.name_fn(self.data)

    @property
    def native_value(self):
        """Return the due time."""
        return self.entity_description.value_fn(self.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""

    api = hass.data[DOMAIN][entry.entry_id]
    course_ids = entry.options["courses"].values()

    async_add_entities(
        (
            CanvasSensorEntity(api, description, course_id)
            for description in SENSOR_DESCRIPTIONS
            for course_id in course_ids
        ),
        update_before_add = True
    )

