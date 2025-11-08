"""Support for Adax energy sensors."""

from __future__ import annotations

from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
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
    """Set up the Adax sensors with config flow."""
    if entry.data.get(CONNECTION_TYPE) != LOCAL:
        cloud_coordinator = cast(AdaxCloudCoordinator, entry.runtime_data)

        # Create individual energy sensors for each device
        sensors: list[AdaxEnergySensor | AdaxTempSensor] = [
            AdaxEnergySensor(cloud_coordinator, device_id)
            for device_id in cloud_coordinator.data
        ]
        sensors.extend(
            AdaxTempSensor(cloud_coordinator, device_id)
            for device_id in cloud_coordinator.data
        )

        async_add_entities(sensors)


class AdaxEnergySensor(CoordinatorEntity[AdaxCloudCoordinator], SensorEntity):
    """Representation of an Adax energy sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "energy"
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
        room = coordinator.data[device_id]

        self._attr_unique_id = f"{room['homeId']}_{device_id}_energy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=room["name"],
            manufacturer="Adax",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and "energyWh" in self.coordinator.data[self._device_id]
        )

    @property
    def native_value(self) -> int:
        """Return the native value of the sensor."""
        return int(self.coordinator.data[self._device_id]["energyWh"])


class AdaxTempSensor(CoordinatorEntity[AdaxCloudCoordinator], SensorEntity):
    """Representation of an Adax temperature sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: AdaxCloudCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        room = coordinator.data[device_id]

        self._attr_unique_id = f"{room['homeId']}_{device_id}_temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and "temperature" in self.coordinator.data[self._device_id]
        )

    @property
    def native_value(self) -> float:
        """Return the native value of the sensor."""
        return float(self.coordinator.data[self._device_id]["temperature"])
