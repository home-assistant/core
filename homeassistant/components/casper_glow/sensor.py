"""Casper Glow integration sensor platform."""

from __future__ import annotations

from pycasperglow import GlowState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CasperGlowConfigEntry, CasperGlowCoordinator
from .entity import CasperGlowEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasperGlowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for Casper Glow."""
    async_add_entities([CasperGlowBatterySensor(entry.runtime_data)])


class CasperGlowBatterySensor(CasperGlowEntity, SensorEntity):
    """Sensor entity for Casper Glow battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{format_mac(coordinator.device.address)}_battery"
        if coordinator.device.state.battery_level is not None:
            self._attr_native_value = coordinator.device.state.battery_level.percentage

    async def async_added_to_hass(self) -> None:
        """Register state update callback when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device.register_callback(self._async_handle_state_update)
        )

    @callback
    def _async_handle_state_update(self, state: GlowState) -> None:
        """Handle a state update from the device."""
        if state.battery_level is not None:
            new_value = state.battery_level.percentage
            if new_value != self._attr_native_value:
                self._attr_native_value = new_value
                self.async_write_ha_state()
