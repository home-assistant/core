"""Casper Glow integration select platform for dimming time."""

from __future__ import annotations

from pycasperglow import GlowState

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DIMMING_TIME_OPTIONS
from .coordinator import CasperGlowConfigEntry, CasperGlowCoordinator
from .entity import CasperGlowEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasperGlowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform for Casper Glow."""
    async_add_entities([CasperGlowDimmingTimeSelect(entry.runtime_data)])


class CasperGlowDimmingTimeSelect(CasperGlowEntity, SelectEntity, RestoreEntity):
    """Select entity for Casper Glow dimming time."""

    _attr_translation_key = "dimming_time"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(DIMMING_TIME_OPTIONS)
    _attr_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize the dimming time select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{format_mac(coordinator.device.address)}_dimming_time"

    @property
    def current_option(self) -> str | None:
        """Return the currently selected dimming time from the coordinator."""
        if self.coordinator.last_dimming_time_minutes is None:
            return None
        return str(self.coordinator.last_dimming_time_minutes)

    async def async_added_to_hass(self) -> None:
        """Restore last known dimming time and register state update callback."""
        await super().async_added_to_hass()
        if self.coordinator.last_dimming_time_minutes is None and (
            last_state := await self.async_get_last_state()
        ):
            if last_state.state in DIMMING_TIME_OPTIONS:
                self.coordinator.last_dimming_time_minutes = int(last_state.state)
        self.async_on_remove(
            self._device.register_callback(self._async_handle_state_update)
        )

    @callback
    def _async_handle_state_update(self, state: GlowState) -> None:
        """Handle a state update from the device."""
        if state.brightness_level is not None:
            self.coordinator.last_brightness_pct = state.brightness_level
        if (
            state.configured_dimming_time_minutes is not None
            and self.coordinator.last_dimming_time_minutes is None
        ):
            self.coordinator.last_dimming_time_minutes = (
                state.configured_dimming_time_minutes
            )
            # Dimming time is not part of the device state
            # that is provided via BLE update. Therefore
            # we need to trigger a state update for the select entity
            # to update the current state.
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Set the dimming time."""
        await self._async_command(
            self._device.set_brightness_and_dimming_time(
                self.coordinator.last_brightness_pct, int(option)
            )
        )
        self.coordinator.last_dimming_time_minutes = int(option)
        # Dimming time is not part of the device state
        # that is provided via BLE update. Therefore
        # we need to trigger a state update for the select entity
        # to update the current state.
        self.async_write_ha_state()
