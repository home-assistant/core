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

        # Create master energy sensor that sums all devices
        master_sensor = AdaxMasterEnergySensor(cloud_coordinator)

        async_add_entities(individual_sensors + [master_sensor])


class AdaxEnergySensor(CoordinatorEntity[AdaxCloudCoordinator], SensorEntity):
    """Representation of an Adax energy sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
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

        self._attr_name = f"{self.room['name']} Energy ({self._device_id})"
        self._attr_unique_id = f"{self.room['homeId']}_{self._device_id}_energy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self.room["name"],
            manufacturer="Adax",
        )
        self._update_native_value()

    @property
    def available(self) -> bool:
        """Whether the entity is available or not."""
        return super().available and self._device_id in self.coordinator.data

    @property
    def room(self) -> dict[str, Any]:
        """Gets the data for this particular device."""
        return self.coordinator.data[self._device_id]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_native_value()
        super()._handle_coordinator_update()

    def _update_native_value(self) -> None:
        """Update the native value based on energy data."""
        energy_wh = self.room.get("energyWh", 0)
        if energy_wh > 0:
            self._attr_native_value = round(energy_wh / 1000, 3)
        else:
            self._attr_native_value = 0.0


class AdaxMasterEnergySensor(CoordinatorEntity[AdaxCloudCoordinator], SensorEntity):
    """Master energy sensor that sums all Adax devices."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
    _attr_name = "Adax Total Energy"

    def __init__(self, coordinator: AdaxCloudCoordinator) -> None:
        """Initialize the master energy sensor."""
        super().__init__(coordinator)

        # Use the first device's homeId for unique_id, or fallback
        first_device = next(iter(coordinator.data.values()), {})
        home_id = first_device.get("homeId", "unknown")

        self._attr_unique_id = f"{home_id}_adax_total_energy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{home_id}_master")},
            name="Adax System",
            manufacturer="Adax",
        )
        self._update_native_value()

    @property
    def available(self) -> bool:
        """Whether the entity is available or not."""
        return super().available and bool(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_native_value()
        super()._handle_coordinator_update()

    def _update_native_value(self) -> None:
        """Update the native value by summing all devices."""
        total_energy_wh = 0
        for room_data in self.coordinator.data.values():
            energy_wh = room_data.get("energyWh", 0)
            if energy_wh > 0:
                total_energy_wh += energy_wh

        if total_energy_wh > 0:
            self._attr_native_value = round(total_energy_wh / 1000, 3)
        else:
            self._attr_native_value = 0.0
