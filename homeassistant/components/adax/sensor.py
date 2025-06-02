"""Support for Adax energy sensors."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AdaxConfigEntry
from .const import CONNECTION_TYPE, DOMAIN, LOCAL
from .coordinator import AdaxCloudCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdaxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Adax energy sensors with config flow."""
    if entry.data.get(CONNECTION_TYPE) != LOCAL:
        cloud_coordinator = cast(AdaxCloudCoordinator, entry.runtime_data)

        # Create individual energy sensors for each device
        individual_sensors = [
            AdaxEnergySensor(cloud_coordinator, device_id)
            for device_id in cloud_coordinator.data
        ]

        async_add_entities(individual_sensors)


class AdaxEnergySensor(CoordinatorEntity[AdaxCloudCoordinator], SensorEntity):
    """Representation of an Adax energy sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: AdaxCloudCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._room = coordinator.data[device_id]

        self._attr_name = f"{self._room['name']} Energy ({self._device_id})"
        self._attr_unique_id = f"{self._room['homeId']}_{self._device_id}_energy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self._room["name"],
            manufacturer="Adax",
        )
        # Set initial native value
        energy_wh = self._room.get("energyWh", 0)

    @property
    def available(self) -> bool:
        """Whether the entity is available or not."""
        return super().available and self._device_id in self.coordinator.data

    @property
    def native_value(self) -> float:
        """Return value of the sensor"""
        return self._room.get("energyWh", 0)
