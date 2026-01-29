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
