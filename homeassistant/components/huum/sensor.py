"""Sensor platform for Huum sauna integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator
from .entity import HuumBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HuumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Huum sensors from a config entry."""
    async_add_entities([HuumTemperatureSensor(config_entry.runtime_data)])


class HuumTemperatureSensor(HuumBaseEntity, SensorEntity):
    """Representation of a Huum temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_temperature"

    @property
    def native_value(self) -> int | None:
        """Return the current temperature."""
        return self.coordinator.data.temperature
