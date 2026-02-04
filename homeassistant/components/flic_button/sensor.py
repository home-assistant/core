"""Sensor platform for Flic Button integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry
from .coordinator import FlicCoordinator
from .entity import FlicButtonEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flic Button sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities([FlicBatterySensor(coordinator)])


class FlicBatterySensor(FlicButtonEntity, SensorEntity):
    """Battery level sensor for Flic button."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery"

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the battery sensor.

        Args:
            coordinator: Flic coordinator instance

        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}-battery"

    @property
    def native_value(self) -> int | None:
        """Return battery level percentage."""
        if self.coordinator.data is None:
            return None

        # Get voltage from coordinator data
        voltage = self.coordinator.data.get("battery_voltage")
        if voltage is None:
            return None

        # Convert voltage to percentage
        # Flic 2 battery voltage ranges from approximately 3.0V (empty) to 3.6V (full)
        # Using linear approximation
        return min(100, max(0, int((voltage - 3.0) / 0.6 * 100)))
