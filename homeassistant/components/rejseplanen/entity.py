"""Base entity for Rejseplanen integration."""

from __future__ import annotations

import logging

from homeassistant.helpers import entity_registry as er
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
        entry_id: str,
        subentry_id: str,
        name: str | None,
        device_id: str | None = None,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)

        self._stop_id = stop_id
        self._entry_id = entry_id
        self._subentry_id = subentry_id
        self._unavailable_logged = False

        # Store device_id for proper association during entity registry
        self._target_device_id = device_id

    async def async_internal_added_to_hass(self) -> None:
        """Handle entity being added to hass - override for device association."""
        # First, call parent to handle normal entity registration
        await super().async_internal_added_to_hass()

        # If we have a target device_id, update the entity registry to associate with device
        if self._target_device_id and self.registry_entry:
            entity_registry = er.async_get(self.hass)
            entity_registry.async_update_entity(
                self.registry_entry.entity_id, device_id=self._target_device_id
            )

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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # Log unavailability changes (Silver requirement)
        if not available and not self._unavailable_logged:
            _LOGGER.info("Entity %s became unavailable", self.entity_id)
            self._unavailable_logged = True
        elif available and self._unavailable_logged:
            _LOGGER.info("Entity %s is back online", self.entity_id)
            self._unavailable_logged = False

        return available
