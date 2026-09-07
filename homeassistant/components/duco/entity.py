"""Base entity for the Duco integration."""

from typing import TYPE_CHECKING, override

from duco_connectivity.models import Node, NodeType

from homeassistant.helpers import device_registry as dr
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
        if TYPE_CHECKING:
            assert mac is not None
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}_{node.node_id}")},
            manufacturer="Duco",
            model=coordinator.board_info.box_name
            if node.general.node_type == NodeType.BOX
            else node.general.node_type,
            name=node.general.name or f"Node {node.node_id}",
        )
        device_info.update(
            {
                "connections": {(CONNECTION_NETWORK_MAC, mac)},
                "serial_number": coordinator.board_info.serial_board_box,
            }
            if node.general.node_type == NodeType.BOX
            # The box is pre-registered in async_setup_entry, so it is always
            # resolvable here even if a sub-node entity is added first.
            else {
                "via_device_id": dr.async_get_device_id_by_identifier(
                    coordinator.hass,
                    (DOMAIN, f"{mac}_1"),
                    config_entry_id=coordinator.config_entry.entry_id,
                )
            }
        )
        self._attr_device_info = device_info

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._node_id in self.coordinator.data.nodes

    @property
    def _node(self) -> Node:
        """Return the current node data from the coordinator."""
        return self.coordinator.data.nodes[self._node_id]
