"""Base entity for the Duco integration."""

from __future__ import annotations

from duco.models import Node

from homeassistant.const import ATTR_VIA_DEVICE
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
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
        assert mac is not None
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}_{node.node_id}")},
            manufacturer="Duco",
            model=coordinator.board_info.box_name
            if node.general.node_type == "BOX"
            else node.general.node_type,
            name=node.general.name or f"Node {node.node_id}",
        )
        device_info.update(
            {
                "connections": {(CONNECTION_NETWORK_MAC, mac)},
                "serial_number": coordinator.board_info.serial_board_box,
            }
            if node.general.node_type == "BOX"
            else {ATTR_VIA_DEVICE: (DOMAIN, f"{mac}_1")}
        )
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._node_id in self.coordinator.data

    @property
    def _node(self) -> Node:
        """Return the current node data from the coordinator."""
        return self.coordinator.data[self._node_id]
