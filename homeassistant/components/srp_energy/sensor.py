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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SRPEnergyDataUpdateCoordinator
from .const import DEFAULT_NAME, DOMAIN, SENSOR_NAME


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SRP Energy Usage sensor."""
    coordinator: SRPEnergyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([SrpEntity(coordinator)])


class SrpEntity(CoordinatorEntity[SRPEnergyDataUpdateCoordinator], SensorEntity):
    """Implementation of a Srp Energy Usage sensor."""

    _attr_attribution = "Powered by SRP Energy"
    _attr_icon = "mdi:flash"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: SRPEnergyDataUpdateCoordinator) -> None:
        """Initialize the SrpEntity class."""
        super().__init__(coordinator)
        self._name = SENSOR_NAME

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME} {self._name}"

    @property
    def native_value(self) -> float:
        """Return the state of the device."""
        return self.coordinator.data
