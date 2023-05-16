"""Support for YouTube Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import YouTubeDataUpdateCoordinator
from .const import (
    ATTR_LATEST_VIDEO,
    ATTR_SUBSCRIBER_COUNT,
    ATTR_THUMBNAIL,
    ATTR_TITLE,
    COORDINATOR,
    DOMAIN,
)
from .entity import YouTubeChannelEntity


@dataclass
class YouTubeMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], StateType]
    entity_picture_fn: Callable[[Any], str]


@dataclass
class YouTubeSensorEntityDescription(SensorEntityDescription, YouTubeMixin):
    """Describes YouTube sensor entity."""


SENSOR_TYPES = [
    YouTubeSensorEntityDescription(
        key="latest_upload",
        translation_key="latest_upload",
        icon="mdi:youtube",
        value_fn=lambda channel: channel[ATTR_LATEST_VIDEO][ATTR_TITLE],
        entity_picture_fn=lambda channel: channel[ATTR_LATEST_VIDEO][ATTR_THUMBNAIL],
    ),
    YouTubeSensorEntityDescription(
        key="subscribers",
        translation_key="subscribers",
        icon="mdi:youtube-subscription",
        native_unit_of_measurement="subscribers",
        value_fn=lambda channel: channel[ATTR_SUBSCRIBER_COUNT],
        entity_picture_fn=lambda channel: channel[ATTR_ICON],
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
        YouTubeSensor(coordinator, sensor_type, channel)
        for channel in coordinator.data.values()
        for sensor_type in SENSOR_TYPES
    )


class YouTubeSensor(YouTubeChannelEntity, SensorEntity):
    """Representation of a YouTube sensor."""

    entity_description: YouTubeSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self._channel)

    @property
    def entity_picture(self) -> str:
        """Return the value reported by the sensor."""
        return self.entity_description.entity_picture_fn(self._channel)
