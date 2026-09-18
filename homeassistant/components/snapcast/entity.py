"""Coordinator entity for Snapcast server."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SnapcastUpdateCoordinator


class SnapcastCoordinatorEntity(CoordinatorEntity[SnapcastUpdateCoordinator]):
    """Coordinator entity for Snapcast."""
