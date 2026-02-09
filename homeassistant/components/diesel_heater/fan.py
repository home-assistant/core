"""Fan platform for Vevor Diesel Heater."""
from __future__ import annotations

PARALLEL_UPDATES = 1

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import VevorHeaterConfigEntry
from .const import (
    DOMAIN,
    MAX_LEVEL,
    MIN_LEVEL,
    RUNNING_MODE_LEVEL,
)
from .coordinator import VevorHeaterCoordinator

_LOGGER = logging.getLogger(__name__)

# Ordered list of levels for percentage conversion
ORDERED_LEVELS = [str(level) for level in range(MIN_LEVEL, MAX_LEVEL + 1)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VevorHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vevor Heater fan from config entry."""
    coordinator = entry.runtime_data
    async_add_entities([VevorHeaterFan(coordinator)])


class VevorHeaterFan(FanEntity):
    """Fan entity for Vevor Heater level control."""

    _attr_has_entity_name = True
    _attr_name = "Heater Level"
    _attr_icon = "mdi:fire"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = MAX_LEVEL

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the fan entity."""
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }
        self._attr_unique_id = f"{coordinator.address}_heater_level"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Only available when connected and in Level mode
        # Manual mode only allows Start/Stop, not level control
        if not self.coordinator.data.get("connected", False):
            return False

        running_mode = self.coordinator.data.get("running_mode")
        return running_mode == RUNNING_MODE_LEVEL

    @property
    def is_on(self) -> bool:
        """Return if the heater is on."""
        return self.coordinator.data.get("running_state", 0) == 1

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        level = self.coordinator.data.get("set_level")
        if level is None:
            return None

        # Convert level (1-10) to percentage (0-100)
        return ordered_list_item_to_percentage(ORDERED_LEVELS, str(level))

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        if percentage == 0:
            # Turn off if percentage is 0
            await self.coordinator.async_turn_off()
            return

        # Convert percentage to level (1-10)
        level_str = percentage_to_ordered_list_item(ORDERED_LEVELS, percentage)
        level = int(level_str)

        _LOGGER.info("Setting heater level to %d (from %d%%)", level, percentage)
        await self.coordinator.async_set_level(level)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the heater."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            # Turn on with current level
            await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the heater."""
        await self.coordinator.async_turn_off()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
