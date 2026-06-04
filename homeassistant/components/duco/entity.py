"""Base entity for the Duco integration."""

from duco_connectivity.models import Node, NodeType

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
        if (mac := coordinator.config_entry.unique_id) is None:
            raise ValueError("Duco config entry unique ID is missing")

        self._is_box = node.general.node_type == NodeType.BOX
        device_name: str
        if self._is_box:
            device_name = node.general.name or coordinator.board_info.box_name
        else:
            device_name = node.general.name or f"Node {node.node_id}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_identifier(node.node_id))},
            manufacturer="Duco",
            model=(
                coordinator.board_info.box_name
                if self._is_box
                else node.general.node_type
            ),
            name=device_name,
            configuration_url=coordinator.configuration_url(
                node.node_id, is_box=self._is_box
            ),
        )
        if self._is_box:
            device_info["connections"] = {(CONNECTION_NETWORK_MAC, mac)}
            device_info["serial_number"] = coordinator.board_info.serial_board_box
            device_info["sw_version"] = coordinator.board_info.software_version
            if model_id := coordinator.board_info.box_sub_type_name:
                device_info["model_id"] = model_id
        else:
            device_info["via_device"] = (DOMAIN, coordinator.device_identifier(1))

        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._node_id in self.coordinator.data.nodes

    @property
    def _node(self) -> Node:
        """Return the current node data from the coordinator."""
        return self.coordinator.data.nodes[self._node_id]
