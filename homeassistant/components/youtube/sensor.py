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
from .api import AsyncConfigEntryAuth
from .const import AUTH, COORDINATOR, DOMAIN
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
        value_fn=lambda channel: channel["latest_video"]["title"],
        entity_picture_fn=lambda channel: channel["latest_video"]["thumbnail"],
    ),
    YouTubeSensorEntityDescription(
        key="subscribers",
        translation_key="subscribers",
        icon="mdi:youtube-subscription",
        native_unit_of_measurement="subscribers",
        value_fn=lambda channel: channel["subscriber_count"],
        entity_picture_fn=lambda channel: channel["icon"],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Google Mail sensor."""
    coordinator: YouTubeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    sensors = []
    for channel in coordinator.data.values():
        sensors += [
            YouTubeSensor(hass.data[DOMAIN][entry.entry_id][AUTH], sensor_type, channel)
            for sensor_type in SENSOR_TYPES
        ]
    async_add_entities(
        sensors,
        True,
    )


class YouTubeSensor(YouTubeChannelEntity, SensorEntity):
    """Representation of a YouTube sensor."""

    _attr_has_entity_name = True

    entity_description: YouTubeSensorEntityDescription

    def __init__(
        self,
        auth: AsyncConfigEntryAuth,
        description: YouTubeSensorEntityDescription,
        channel: dict[str, Any],
    ) -> None:
        """Initialize YouTube Sensor."""
        super().__init__(auth, description, channel["title"])
        self._channel = channel

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self._channel)

    @property
    def entity_picture(self) -> str:
        """Return the value reported by the sensor."""
        return self.entity_description.entity_picture_fn(self._channel)
