"""Loqed sensor entities."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoqedDataCoordinator
from .const import DOMAIN

SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        name="Battery",
        key="battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        name="Wi-Fi signal",
        key="wifi_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        name="Bluetooth signal",
        key="ble_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
        icon="mdi:signal",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Loqed sensor."""
    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(LoqedSensor(sensor, coordinator) for sensor in SENSORS)


class LoqedSensor(CoordinatorEntity[LoqedDataCoordinator], SensorEntity):
    """Class representing a LoqedSensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        sensor_description: SensorEntityDescription,
        coordinator: LoqedDataCoordinator,
    ) -> None:
        """Initialize the loqed sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.lock.id)},
            name="Loqed instance",
        )
        self.entity_description = sensor_description
        self._attr_unique_id = f"{sensor_description.key}-{coordinator.lock.id}"
        self._attr_native_value = coordinator.data[sensor_description.key]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        key = self.entity_description.key

        if key in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[key]
            self.async_write_ha_state()
