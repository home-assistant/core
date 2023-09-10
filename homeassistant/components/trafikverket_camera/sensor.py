"""Sensor platform for Trafikverket Camera integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CameraData, TVDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Trafikverket Camera base description keys."""

    value_fn: Callable[[CameraData], StateType | datetime]


@dataclass
class TVCameraSensorEntityDescription(
    SensorEntityDescription, DeviceBaseEntityDescriptionMixin
):
    """Describes Trafikverket Camera sensor entity."""


SENSOR_TYPES: tuple[TVCameraSensorEntityDescription, ...] = (
    TVCameraSensorEntityDescription(
        key="direction",
        translation_key="direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:sign-direction",
        value_fn=lambda data: data.data.direction,
    ),
    TVCameraSensorEntityDescription(
        key="modified",
        translation_key="modified",
        icon="mdi:camera-retake-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.data.modified,
        entity_registry_enabled_default=False,
    ),
    TVCameraSensorEntityDescription(
        key="photo_time",
        translation_key="photo_time",
        icon="mdi:camera-timer",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.data.phototime,
    ),
    TVCameraSensorEntityDescription(
        key="photo_url",
        translation_key="photo_url",
        icon="mdi:camera-outline",
        value_fn=lambda data: data.data.photourl,
        entity_registry_enabled_default=False,
    ),
    TVCameraSensorEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:camera-outline",
        value_fn=lambda data: data.data.status,
        entity_registry_enabled_default=False,
    ),
    TVCameraSensorEntityDescription(
        key="camera_type",
        translation_key="camera_type",
        icon="mdi:camera-iris",
        value_fn=lambda data: data.data.camera_type,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Trafikverket Camera sensor platform."""

    coordinator: TVDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TrafikverketCameraSensor(coordinator, entry.entry_id, entry.title, description)
        for description in SENSOR_TYPES
    )


class TrafikverketCameraSensor(
    CoordinatorEntity[TVDataUpdateCoordinator], SensorEntity
):
    """Representation of a Trafikverket Camera Sensor."""

    entity_description: TVCameraSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        entry_id: str,
        name: str,
        entity_description: TVCameraSensorEntityDescription,
    ) -> None:
        """Initiate Trafikverket Camera Sensor."""
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
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()
