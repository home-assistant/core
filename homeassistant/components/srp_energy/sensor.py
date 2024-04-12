"""Support for SRP Energy Sensor."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SRPEnergyDataUpdateCoordinator
from .const import DEVICE_CONFIG_URL, DEVICE_MANUFACTURER, DEVICE_MODEL, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SRP Energy Usage sensor."""
    coordinator: SRPEnergyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([SrpEntity(coordinator, entry)])


class SrpEntity(CoordinatorEntity[SRPEnergyDataUpdateCoordinator], SensorEntity):
    """Implementation of a Srp Energy Usage sensor."""

    _attr_attribution = "Powered by SRP Energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_has_entity_name = True
    _attr_translation_key = "energy_usage"

    def __init__(
        self,
        coordinator: SRPEnergyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the SrpEntity class."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_total_usage"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"SRP Energy {config_entry.title}",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            configuration_url=DEVICE_CONFIG_URL,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self.coordinator.data
