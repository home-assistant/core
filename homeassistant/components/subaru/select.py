"""Support for Subaru climate preset select."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_info
from .const import (
    VEHICLE_CLIMATE,
    VEHICLE_CLIMATE_PRESET_NAME,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_START,
    VEHICLE_VIN,
)
from .coordinator import SubaruConfigEntry, SubaruDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SubaruConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Subaru climate preset select by config_entry."""
    coordinator = config_entry.runtime_data.coordinator
    vehicle_info = config_entry.runtime_data.vehicles
    async_add_entities(
        SubaruClimateSelect(vehicle, coordinator)
        for vehicle in vehicle_info.values()
        if vehicle[VEHICLE_HAS_REMOTE_START] or vehicle[VEHICLE_HAS_EV]
    )


class SubaruClimateSelect(
    CoordinatorEntity[SubaruDataUpdateCoordinator], SelectEntity, RestoreEntity
):
    """Representation of a Subaru climate preset select entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "climate_preset"

    def __init__(
        self,
        vehicle_info: dict[str, Any],
        coordinator: SubaruDataUpdateCoordinator,
    ) -> None:
        """Initialize the select entity for the vehicle."""
        super().__init__(coordinator)
        self.vin = vehicle_info[VEHICLE_VIN]
        self._attr_current_option = None
        self._attr_device_info = get_device_info(vehicle_info)
        self._attr_unique_id = f"{self.vin}_{VEHICLE_CLIMATE}"

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        if self.coordinator.data and (
            vehicle_data := self.coordinator.data.get(self.vin)
        ):
            if isinstance(preset_data := vehicle_data.get(VEHICLE_CLIMATE), list):
                return [preset[VEHICLE_CLIMATE_PRESET_NAME] for preset in preset_data]
        return []

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        last_update_success = super().available
        if last_update_success and self.vin not in self.coordinator.data:
            return False
        return last_update_success

    async def async_added_to_hass(self) -> None:
        """Restore previous state of this select entity."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state in self.options:
            self._attr_current_option = state.state
            self.coordinator.config_entry.runtime_data.climate_presets[self.vin] = (
                state.state
            )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self.coordinator.config_entry.runtime_data.climate_presets[self.vin] = option
        self.async_write_ha_state()
