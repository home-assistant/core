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
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CameraData, TVDataUpdateCoordinator

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
                coordinator, entry.entry_id, entry.title, BINARY_SENSOR_TYPE
            )
        ]
    )


class TrafikverketCameraBinarySensor(
    CoordinatorEntity[TVDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Trafikverket Camera binary sensor."""

    entity_description: TVCameraSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        entry_id: str,
        name: str,
        entity_description: TVCameraSensorEntityDescription,
    ) -> None:
        """Initiate Trafikverket Camera Binary sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v1.0",
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )
        self._update_attr()

    @callback
    def _update_attr(self) -> None:
        """Update _attr."""
        self._attr_is_on = self.entity_description.value_fn(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()
