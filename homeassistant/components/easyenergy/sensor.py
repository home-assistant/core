"""Support for easyEnergy sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_TYPE_DEVICE_NAMES
from .coordinator import EasyEnergyData, EasyEnergyDataUpdateCoordinator


@dataclass
class EasyEnergySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EasyEnergyData], float | datetime | None]
    service_type: str


@dataclass
class EasyEnergySensorEntityDescription(SensorEntityDescription):
    """Describes easyEnergy sensor entity."""


class EasyEnergySensorEntity(
    CoordinatorEntity[EasyEnergyDataUpdateCoordinator], SensorEntity
):
    """Defines a easyEnergy sensor."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by easyEnergy"
    entity_description: EasyEnergySensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: EasyEnergyDataUpdateCoordinator,
        description: EasyEnergySensorEntityDescription,
    ) -> None:
        """Initialize easyEnergy sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.entity_id = (
            f"{SENSOR_DOMAIN}.{DOMAIN}_{description.service_type}_{description.key}"
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.service_type}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}_{description.service_type}",
                )
            },
            manufacturer="easyEnergy",
            name=SERVICE_TYPE_DEVICE_NAMES[self.entity_description.service_type],
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
