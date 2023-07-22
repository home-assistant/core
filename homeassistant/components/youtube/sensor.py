"""Support for YouTube Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import YouTubeDataUpdateCoordinator
from .const import (
    ATTR_PUBLISHED_AT,
    ATTR_VIDEO_ID,
    COORDINATOR,
    DOMAIN,
)
from .coordinator import YouTubeHAData
from .entity import YouTubeChannelEntity


@dataclass
class YouTubeMixin:
    """Mixin for required keys."""

    value_fn: Callable[[YouTubeHAData], StateType]
    entity_picture_fn: Callable[[YouTubeHAData], str | None]
    attributes_fn: Callable[[YouTubeHAData], dict[str, Any]] | None


@dataclass
class YouTubeSensorEntityDescription(SensorEntityDescription, YouTubeMixin):
    """Describes YouTube sensor entity."""


SENSOR_TYPES = [
    YouTubeSensorEntityDescription(
        key="latest_upload",
        translation_key="latest_upload",
        icon="mdi:youtube",
        value_fn=lambda youtube_data: youtube_data.latest_video.snippet.title
        if youtube_data.latest_video
        else None,
        entity_picture_fn=lambda youtube_data: youtube_data.latest_video.snippet.thumbnails.get_highest_quality().url
        if youtube_data.latest_video
        else None,
        attributes_fn=lambda youtube_data: {
            ATTR_VIDEO_ID: youtube_data.latest_video.content_details.video_id
            if youtube_data.latest_video
            else None,
            ATTR_PUBLISHED_AT: youtube_data.latest_video.snippet.added_at
            if youtube_data.latest_video
            else None,
        },
    ),
    YouTubeSensorEntityDescription(
        key="subscribers",
        translation_key="subscribers",
        icon="mdi:youtube-subscription",
        native_unit_of_measurement="subscribers",
        value_fn=lambda youtube_data: youtube_data.channel.statistics.subscriber_count,
        entity_picture_fn=lambda youtube_data: youtube_data.channel.snippet.thumbnails.get_highest_quality().url,
        attributes_fn=None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._channel_id])

    @property
    def entity_picture(self) -> str | None:
        """Return the value reported by the sensor."""
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
