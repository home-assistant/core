"""Base entity for the Duco integration."""

from __future__ import annotations

from duco.models import Node

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DucoCoordinator


class DucoEntity(CoordinatorEntity[DucoCoordinator]):
    """Base class for Duco entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DucoCoordinator, node_id: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._node_id = node_id

    @property
    def _node(self) -> Node | None:
        """Return the current node data from the coordinator."""
        return next(
            (n for n in self.coordinator.data if n.node_id == self._node_id),
            None,
        )
