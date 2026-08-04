"""Support for IntelliClima Binary Sensors."""

from typing import override

from pyintelliclima.intelliclima_types import IntelliClimaECO

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntelliClimaConfigEntry, IntelliClimaFilterCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a IntelliClima On/Off Sensor."""
    data = entry.runtime_data

    async_add_entities(
        IntelliClimaFilterCleaningBinarySensor(
            coordinator=data.filter_coordinator, device=ecocomfort2
        )
        for ecocomfort2 in data.devices_coordinator.data.ecocomfort2_devices.values()
    )


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
        return (
            super().available
            and self._device_sn in self.coordinator.data
            and self.coordinator.data[self._device_sn].is_active
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the filter needs cleaning."""
        return self.coordinator.data[self._device_sn].change_filter
