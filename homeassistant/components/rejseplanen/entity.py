"""Base entity for Rejseplanen integration."""

from __future__ import annotations

import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class RejseplanenEntity(CoordinatorEntity[RejseplanenDataUpdateCoordinator]):
    """Base Rejseplanen entity."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by rejseplanen.dk"

    def __init__(
        self,
        coordinator: RejseplanenDataUpdateCoordinator,
        stop_id: int,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator, context=stop_id)

        self._stop_id = stop_id

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to hass."""
        await super().async_added_to_hass()
        # Register stop ID with coordinator
        self.coordinator.add_stop_id(self._stop_id)

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal of the entity from Home Assistant."""
        await super().async_will_remove_from_hass()
        # Clean up stop ID from coordinator
        self.coordinator.remove_stop_id(self._stop_id)
