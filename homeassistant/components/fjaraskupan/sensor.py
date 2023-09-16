"""Support for sensors."""
from __future__ import annotations

from fjaraskupan import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_setup_entry_platform
from .coordinator import FjaraskupanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors dynamically through discovery."""

    def _constructor(coordinator: FjaraskupanCoordinator) -> list[Entity]:
        return [RssiSensor(coordinator, coordinator.device, coordinator.device_info)]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class RssiSensor(CoordinatorEntity[FjaraskupanCoordinator], SensorEntity):
    """Sensor device."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FjaraskupanCoordinator,
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-signal-strength"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        if data := self.coordinator.data:
            return data.rssi
        return None
