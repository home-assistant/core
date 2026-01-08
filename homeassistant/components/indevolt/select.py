"""Select platform for indevolt integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator

_LOGGER = logging.getLogger(__name__)

WORKING_MODE_MAP = {
    1: "self_consumed_prioritized",
    4: "real_time_control",
    5: "charge_discharge_schedule",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform for Indevolt."""
    coordinator = entry.runtime_data

    async_add_entities([IndevoltWorkingModeSelect(coordinator)])


class IndevoltWorkingModeSelect(CoordinatorEntity[IndevoltCoordinator], SelectEntity):
    """Select entity for Working Mode selection."""

    _attr_has_entity_name = True
    _attr_translation_key = "working_mode"

    def __init__(self, coordinator: IndevoltCoordinator) -> None:
        """Initialize the Working Mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_working_mode"
        self._attr_options = list(WORKING_MODE_MAP.values())
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None

        mode_value = self.coordinator.data.get("7101")

        if mode_value is None:
            return None

        try:
            mode_int = int(mode_value) if isinstance(mode_value, str) else mode_value
        except (ValueError, TypeError):
            _LOGGER.error(
                "Invalid working mode value: %s (type: %s)",
                mode_value,
                type(mode_value),
            )
            return None

        option = WORKING_MODE_MAP.get(mode_int)
        if option is None:
            _LOGGER.warning(
                "Mode value %s not found in map. Valid values: %s",
                mode_int,
                list(WORKING_MODE_MAP.keys()),
            )

        return option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode_value = next(
            (key for key, value in WORKING_MODE_MAP.items() if value == option),
            None,
        )

        if mode_value is None:
            _LOGGER.error("Invalid working mode option: %s", option)
            return

        try:
            await self.coordinator.async_push_data("47005", mode_value)
            await self.coordinator.async_request_refresh()

        except Exception:
            _LOGGER.exception("Failed to set working mode to %s", option)
            raise
