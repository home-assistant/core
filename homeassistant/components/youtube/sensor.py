"""Support for YouTube Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import YouTubeDataUpdateCoordinator
from .const import (
    ATTR_LATEST_VIDEO,
    ATTR_PUBLISHED_AT,
    ATTR_SUBSCRIBER_COUNT,
    ATTR_THUMBNAIL,
    ATTR_TITLE,
    ATTR_TOTAL_VIEWS,
    ATTR_VIDEO_ID,
    COORDINATOR,
    DOMAIN,
)
from .entity import YouTubeChannelEntity


@dataclass(frozen=True, kw_only=True)
class YouTubeSensorEntityDescription(SensorEntityDescription):
    """Describes YouTube sensor entity."""

    available_fn: Callable[[Any], bool]
    value_fn: Callable[[Any], StateType]
    entity_picture_fn: Callable[[Any], str | None]
    attributes_fn: Callable[[Any], dict[str, Any] | None] | None


SENSOR_TYPES = [
    YouTubeSensorEntityDescription(
        key="latest_upload",
        translation_key="latest_upload",
        available_fn=lambda channel: channel[ATTR_LATEST_VIDEO] is not None,
        value_fn=lambda channel: channel[ATTR_LATEST_VIDEO][ATTR_TITLE],
        entity_picture_fn=lambda channel: channel[ATTR_LATEST_VIDEO][ATTR_THUMBNAIL],
        attributes_fn=lambda channel: {
            ATTR_VIDEO_ID: channel[ATTR_LATEST_VIDEO][ATTR_VIDEO_ID],
            ATTR_PUBLISHED_AT: channel[ATTR_LATEST_VIDEO][ATTR_PUBLISHED_AT],
        },
    ),
    YouTubeSensorEntityDescription(
        key="subscribers",
        translation_key="subscribers",
        native_unit_of_measurement="subscribers",
        available_fn=lambda _: True,
        value_fn=lambda channel: channel[ATTR_SUBSCRIBER_COUNT],
        entity_picture_fn=lambda channel: channel[ATTR_ICON],
        attributes_fn=None,
    ),
    YouTubeSensorEntityDescription(
        key="views",
        translation_key="views",
        native_unit_of_measurement="views",
        available_fn=lambda _: True,
        value_fn=lambda channel: channel[ATTR_TOTAL_VIEWS],
        entity_picture_fn=lambda channel: channel[ATTR_ICON],
        attributes_fn=None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the YouTube sensor."""
    coordinator: YouTubeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    async_add_entities(
        YouTubeSensor(coordinator, sensor_type, channel_id)
        for channel_id in coordinator.data
        for sensor_type in SENSOR_TYPES
    )


class YouTubeSensor(YouTubeChannelEntity, SensorEntity):
    """Representation of a YouTube sensor."""

    entity_description: YouTubeSensorEntityDescription

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data[self._channel_id]
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._channel_id])

    @property
    def entity_picture(self) -> str | None:
        """Return the value reported by the sensor."""
        if not self.available:
            return None
        return self.entity_description.entity_picture_fn(
            self.coordinator.data[self._channel_id]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(
                self.coordinator.data[self._channel_id]
            )
        return None
