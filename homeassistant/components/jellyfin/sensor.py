"""Support for Jellyfin sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import JellyfinConfigEntry, JellyfinDataUpdateCoordinator
from .entity import JellyfinServerEntity


@dataclass(frozen=True, kw_only=True)
class JellyfinSensorEntityDescription(SensorEntityDescription):
    """Describes Jellyfin sensor entity."""

    value_fn: Callable[[dict[str, dict[str, Any]]], StateType]


def _count_now_playing(data: dict[str, dict[str, Any]]) -> int:
    """Count the number of now playing."""
    session_ids = [
        sid for (sid, session) in data.items() if "NowPlayingItem" in session
    ]

    return len(session_ids)


SENSOR_TYPES: tuple[JellyfinSensorEntityDescription, ...] = (
    JellyfinSensorEntityDescription(
        key="watching",
        translation_key="watching",
        value_fn=_count_now_playing,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin sensor based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        JellyfinServerSensor(coordinator, description) for description in SENSOR_TYPES
    )


class JellyfinServerSensor(JellyfinServerEntity, SensorEntity):
    """Defines a Jellyfin sensor entity."""

    entity_description: JellyfinSensorEntityDescription

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        description: JellyfinSensorEntityDescription,
    ) -> None:
        """Initialize Jellyfin sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.server_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
