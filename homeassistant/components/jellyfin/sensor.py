"""Support for Jellyfin sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import JellyfinDataT
from .entity import JellyfinEntity
from .models import JellyfinData


@dataclass(frozen=True, kw_only=True)
class JellyfinSensorEntityDescription(SensorEntityDescription):
    """Describes Jellyfin sensor entity."""

    value_fn: Callable[[JellyfinDataT], StateType]


def _count_now_playing(data: JellyfinDataT) -> int:
    """Count the number of now playing."""
    session_ids = [
        sid for (sid, session) in data.items() if "NowPlayingItem" in session
    ]

    return len(session_ids)


SENSOR_TYPES: dict[str, JellyfinSensorEntityDescription] = {
    "sessions": JellyfinSensorEntityDescription(
        key="watching",
        translation_key="watching",
        name=None,
        native_unit_of_measurement="Watching",
        value_fn=_count_now_playing,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin sensor based on a config entry."""
    jellyfin_data: JellyfinData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        JellyfinSensor(jellyfin_data.coordinators[coordinator_type], description)
        for coordinator_type, description in SENSOR_TYPES.items()
    )


class JellyfinSensor(JellyfinEntity, SensorEntity):
    """Defines a Jellyfin sensor entity."""

    entity_description: JellyfinSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
