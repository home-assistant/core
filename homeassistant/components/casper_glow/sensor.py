"""Casper Glow integration sensor platform."""

from __future__ import annotations

from datetime import datetime, timedelta

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
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from .coordinator import CasperGlowConfigEntry, CasperGlowCoordinator
from .entity import CasperGlowEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasperGlowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for Casper Glow."""
    async_add_entities(
        [
            CasperGlowBatterySensor(entry.runtime_data),
            CasperGlowDimmingEndTimeSensor(entry.runtime_data),
        ]
    )


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


class CasperGlowDimmingEndTimeSensor(CasperGlowEntity, SensorEntity):
    """Sensor entity for Casper Glow dimming end time."""

    _attr_translation_key = "dimming_end_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize the dimming end time sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{format_mac(coordinator.device.address)}_dimming_end_time"
        )
        self._is_paused = False
        self._projected_end_time = ignore_variance(
            self._calculate_end_time,
            timedelta(minutes=1, seconds=30),
        )
        self._update_from_state(coordinator.device.state)

    @staticmethod
    def _calculate_end_time(remaining_ms: int) -> datetime:
        """Calculate projected dimming end time from remaining milliseconds."""
        return utcnow() + timedelta(milliseconds=remaining_ms)

    async def async_added_to_hass(self) -> None:
        """Register state update callback when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device.register_callback(self._async_handle_state_update)
        )

    def _reset_projected_end_time(self) -> None:
        """Clear the projected end time and reset the variance filter."""
        self._attr_native_value = None
        self._projected_end_time = ignore_variance(
            self._calculate_end_time,
            timedelta(minutes=1, seconds=30),
        )

    @callback
    def _update_from_state(self, state: GlowState) -> None:
        """Update entity attributes from device state."""
        if state.is_paused is not None:
            self._is_paused = state.is_paused

        if self._is_paused:
            self._reset_projected_end_time()
            return

        remaining_ms = state.dimming_time_remaining_ms
        if not remaining_ms:
            if remaining_ms == 0 or state.is_on is False:
                self._reset_projected_end_time()
            return
        self._attr_native_value = self._projected_end_time(remaining_ms)

    @callback
    def _async_handle_state_update(self, state: GlowState) -> None:
        """Handle a state update from the device."""
        self._update_from_state(state)
        self.async_write_ha_state()
