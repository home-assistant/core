"""Binary sensor platform for Trafikverket Camera integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CameraData, TVDataUpdateCoordinator
from .entity import TrafikverketCameraNonCameraEntity

PARALLEL_UPDATES = 0


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Trafikverket Camera base description keys."""

    value_fn: Callable[[CameraData], bool | None]


@dataclass
class TVCameraSensorEntityDescription(
    BinarySensorEntityDescription, DeviceBaseEntityDescriptionMixin
):
    """Describes Trafikverket Camera binary sensor entity."""


BINARY_SENSOR_TYPE = TVCameraSensorEntityDescription(
    key="active",
    translation_key="active",
    icon="mdi:camera-outline",
    value_fn=lambda data: data.data.active,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Trafikverket Camera binary sensor platform."""

    coordinator: TVDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
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
