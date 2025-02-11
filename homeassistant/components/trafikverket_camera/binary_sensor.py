"""Binary sensor platform for Trafikverket Camera integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TVCameraConfigEntry
from .coordinator import CameraData
from .entity import TrafikverketCameraNonCameraEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TVCameraSensorEntityDescription(BinarySensorEntityDescription):
    """Describes Trafikverket Camera binary sensor entity."""

    value_fn: Callable[[CameraData], bool | None]


BINARY_SENSOR_TYPE = TVCameraSensorEntityDescription(
    key="active",
    translation_key="active",
    value_fn=lambda data: data.data.active,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TVCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trafikverket Camera binary sensor platform."""

    coordinator = entry.runtime_data
    async_add_entities(
        [
            TrafikverketCameraBinarySensor(
                coordinator, entry.entry_id, BINARY_SENSOR_TYPE
            )
        ]
    )


class TrafikverketCameraBinarySensor(
    TrafikverketCameraNonCameraEntity, BinarySensorEntity
):
    """Representation of a Trafikverket Camera binary sensor."""

    entity_description: TVCameraSensorEntityDescription

    @callback
    def _update_attr(self) -> None:
        """Update _attr."""
        self._attr_is_on = self.entity_description.value_fn(self.coordinator.data)
