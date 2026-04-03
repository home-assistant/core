"""Base entity for the Duco integration."""

from __future__ import annotations

from duco.models import Node

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DucoCoordinator


class DucoEntity(CoordinatorEntity[DucoCoordinator]):
    """Base class for Duco entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DucoCoordinator, node: Node) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._node_id = node.node_id
        mac = coordinator.config_entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}_{node.node_id}")},
            manufacturer="Duco",
            model=coordinator.board_info.box_name
            if node.general.node_type == "BOX"
            else node.general.node_type,
            name=node.general.name or f"Node {node.node_id}",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._node is not None

    @property
    def _node(self) -> Node | None:
        """Return the current node data from the coordinator."""
        return self.coordinator.data.get(self._node_id)
