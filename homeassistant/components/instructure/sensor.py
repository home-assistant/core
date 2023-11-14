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

from .api_wrapper import ApiWrapper

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

    api_endpoint_function: Callable = None

    def fetch_data(self):
        return self.api_endpoint_function()

api_wrapper = ApiWrapper("https://canvas.instructure.com/api/v1/", "")

SENSOR_DESCRIPTIONS: tuple[CanvasSensorEntityDescription, ...] = (
    CanvasSensorEntityDescription(
        key="upcoming_assignments",
        translation_key="upcoming_assignments",
        # name_fn=lambda data: str(data["course_id"]) + "-" + data["name"],
        name_fn=lambda data: "Assignments",
        value_fn=lambda data: datetime_process(data["due_at"]),
        attr_fn=lambda data: {
            "Link": data["html_url"]
        },
        api_endpoint_function= lambda: api_wrapper.async_get_assignments("100")
    ),

    # CanvasSensorEntityDescription(
    #     key="inbox",
    #     translation_key="inbox",
    #     name_fn=lambda data: ", ".join([p["full_name"] for p in data["participants"]]),
    #     value_fn=lambda data: {
    #         "Date": data["start_at"],
    #         "Subject": data["subject"],
    #         "Last message": data["last_message"]
    #     },
    #     api_endpoint_function=lambda _: api_wrapper.async_get_conversations,
    # )
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

    async def async_update(self):
        # TODO: Add try-catch
        # self.data = await self.entity_description.api_endpoint_function(100)
        self.data = await self.entity_description.fetch_data();

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.entity_description.name_fn(self.data)

    @property
    def native_value(self):
        """Return the due time."""
        return self.entity_description.value_fn(self.data)

    # @property
    # def extra_state_attributes(self):
    #     """Return the state attributes like assignment links."""
    #     return self.entity_description.attr_fn(self.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""

    async_add_entities(
        (
            CanvasSensorEntity(description)
            for description in SENSOR_DESCRIPTIONS
        ),
        update_before_add = True
    )

