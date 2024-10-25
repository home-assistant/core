"""Coordinator entity for Snapcast server."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SnapcastUpdateCoordinator


class SnapcastCoordinatorEntity(CoordinatorEntity[SnapcastUpdateCoordinator]):
    """Coordinator entity for Snapcast."""

    def __init__(self, coordinator: SnapcastUpdateCoordinator) -> None:
        """Create a Snapcast entity with an update coordinator."""
        super().__init__(coordinator)
