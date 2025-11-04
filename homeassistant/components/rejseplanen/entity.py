"""Base entity for Rejseplanen integration."""

from __future__ import annotations

import logging

from homeassistant.helpers.device_registry import DeviceInfo
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

        # If device_id is provided, use it directly for device association
        if device_id:
            # Set the device_id to associate with the pre-created device
            self._attr_device_id = device_id
        else:
            # Only create DeviceInfo if no device_id was provided (legacy fallback)
            self._attr_device_info = DeviceInfo(
                identifiers={
                    (
                        "rejseplanen",
                        f"{entry_id}-subentry-{subentry_id}"
                        if subentry_id != entry_id
                        else f"{entry_id}-stop-{stop_id}",
                    )
                },
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
