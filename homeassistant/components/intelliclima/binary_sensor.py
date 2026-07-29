"""Support for IntelliClima Binary Sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyintelliclima.intelliclima_types import IntelliClimaECO

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    IntelliClimaConfigEntry,
    IntelliClimaCoordinator,
    IntelliClimaFilterCoordinator,
)
from .entity import IntelliClimaECOEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class IntelliClimaBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[IntelliClimaECO], bool | None]


@dataclass(frozen=True)
class IntelliClimaBinarySensorEntityDescription(
    BinarySensorEntityDescription, IntelliClimaBinarySensorRequiredKeysMixin
):
    """Describes a binary sensor entity."""


INTELLICLIMA_BINARY_SENSORS: tuple[IntelliClimaBinarySensorEntityDescription, ...] = (
    IntelliClimaBinarySensorEntityDescription(
        key="master_satellite",
        translation_key="master_satellite",
        value_fn=lambda device_data: device_data.role == "1",
    ),
    IntelliClimaBinarySensorEntityDescription(
        key="winter_summer",
        translation_key="winter_summer",
        value_fn=lambda device_data: device_data.ws == "0",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a IntelliClima On/Off Sensor."""
    data = entry.runtime_data

    entities: list[BinarySensorEntity] = []
    for ecocomfort2 in data.devices_coordinator.data.ecocomfort2_devices.values():
        entities.extend(
            IntelliClimaBinarySensor(
                coordinator=data.devices_coordinator,
                device=ecocomfort2,
                description=description,
            )
            for description in INTELLICLIMA_BINARY_SENSORS
        )
        entities.append(
            IntelliClimaFilterCleaningBinarySensor(
                coordinator=data.filter_coordinator, device=ecocomfort2
            )
        )

    async_add_entities(entities)


class IntelliClimaBinarySensor(IntelliClimaECOEntity, BinarySensorEntity):
    """Extends IntelliClimaEntity with Binary Sensor specific logic."""

    entity_description: IntelliClimaBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO,
        description: IntelliClimaBinarySensorEntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self.entity_description = description

        self._attr_unique_id = f"{device.id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Use this to get the correct value."""
        return self.entity_description.value_fn(self._device_data)


class IntelliClimaFilterCleaningBinarySensor(
    CoordinatorEntity[IntelliClimaFilterCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether the device's filter needs cleaning."""

    _attr_has_entity_name = True
    _attr_translation_key = "filter_cleaning"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: IntelliClimaFilterCoordinator,
        device: IntelliClimaECO,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device.id)})
        self._device_sn = device.crono_sn
        self._attr_unique_id = f"{device.id}_filter_cleaning"

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device_sn in self.coordinator.data

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the filter needs cleaning."""
        return self.coordinator.data[self._device_sn].change_filter
