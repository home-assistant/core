"""Sensor platform for the Immich integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ImmichConfigEntry, ImmichData, ImmichDataUpdateCoordinator
from .entity import ImmichEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ImmichSensorEntityDescription(SensorEntityDescription):
    """IMGW-PIB sensor entity description."""

    value: Callable[[ImmichData], StateType]


SENSOR_TYPES: tuple[ImmichSensorEntityDescription, ...] = (
    ImmichSensorEntityDescription(
        key="disk_size",
        translation_key="disk_size",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_storage.disk_size_raw,
    ),
    ImmichSensorEntityDescription(
        key="disk_available",
        translation_key="disk_available",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_storage.disk_available_raw,
    ),
    ImmichSensorEntityDescription(
        key="disk_use",
        translation_key="disk_use",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_storage.disk_use_raw,
        entity_registry_enabled_default=False,
    ),
    ImmichSensorEntityDescription(
        key="disk_usage",
        translation_key="disk_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_storage.disk_usage_percentage,
        entity_registry_enabled_default=False,
    ),
    ImmichSensorEntityDescription(
        key="photos_count",
        translation_key="photos_count",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_usage.photos,
    ),
    ImmichSensorEntityDescription(
        key="videos_count",
        translation_key="videos_count",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_usage.videos,
    ),
    ImmichSensorEntityDescription(
        key="usage_by_photos",
        translation_key="usage_by_photos",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_usage.usage_photos,
        entity_registry_enabled_default=False,
    ),
    ImmichSensorEntityDescription(
        key="usage_by_videos",
        translation_key="usage_by_videos",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.server_usage.usage_videos,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add immich server state sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ImmichSensorEntity(coordinator, description) for description in SENSOR_TYPES
    )


class ImmichSensorEntity(ImmichEntity, SensorEntity):
    """Define IMGW-PIB sensor entity."""

    entity_description: ImmichSensorEntityDescription

    def __init__(
        self,
        coordinator: ImmichDataUpdateCoordinator,
        description: ImmichSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self.coordinator.data)
