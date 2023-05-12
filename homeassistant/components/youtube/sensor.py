"""Support for Google Mail Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import YouTubeDataUpdateCoordinator
from .api import AsyncConfigEntryAuth
from .const import AUTH, COORDINATOR, DOMAIN, MANUFACTURER
from .entity import YouTubeEntity

SCAN_INTERVAL = timedelta(minutes=15)


@dataclass
class YouTubeMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], StateType]
    entity_picture_fn: Callable[[Any], str] | None


@dataclass
class YouTubeSensorEntityDescription(SensorEntityDescription, YouTubeMixin):
    """Describes Picnic sensor entity."""


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
    for channel in coordinator.data.values():
        async_add_entities(
            [
                YouTubeSensor(
                    hass.data[DOMAIN][entry.entry_id][AUTH], sensor_type, channel
                )
                for sensor_type in SENSOR_TYPES
            ],
            True,
        )


class YouTubeSensor(YouTubeEntity, SensorEntity):
    """Representation of a Google Mail sensor."""

    _attr_has_entity_name = True

    entity_description: YouTubeSensorEntityDescription

    def __init__(
        self,
        auth: AsyncConfigEntryAuth,
        description: YouTubeSensorEntityDescription,
        channel: dict[str, Any],
    ) -> None:
        super().__init__(auth, description)
        self._channel = channel
        channel_id = channel["id"]
        self._attr_unique_id = (
            f"{auth.oauth_session.config_entry.entry_id}_{channel_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, auth.oauth_session.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=self._channel["title"],
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self._channel)

    @property
    def entity_picture(self) -> str | None:
        """Return the value reported by the sensor."""
        if self.entity_description.entity_picture_fn:
            return self.entity_description.entity_picture_fn(self._channel)
        return None
