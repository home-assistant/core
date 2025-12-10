"""Base entity for the Autarco integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AutarcoDataUpdateCoordinator


class AutarcoEntity(CoordinatorEntity[AutarcoDataUpdateCoordinator]):
    """Defines a base Autarco entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AutarcoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Autarco entity."""
        super().__init__(coordinator)
