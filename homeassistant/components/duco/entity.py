"""Base entity for the Duco integration."""

from duco_connectivity.models import Node, NodeType

from homeassistant.const import CONF_HOST
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
        if mac is None:
            msg = "Config entry unique_id is required for Duco device registration"
            raise ValueError(msg)

        is_box = node.general.node_type == NodeType.BOX

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_identifier(mac, node.node_id))},
            manufacturer="Duco",
            model=(
                coordinator.board_info.box_name if is_box else node.general.node_type
            ),
            name=(
                (node.general.name or coordinator.board_info.box_name)
                if is_box
                else (node.general.name or f"Node {node.node_id}")
            ),
            configuration_url=self._configuration_url(coordinator, node, is_box),
        )
        if is_box:
            device_info["connections"] = {(CONNECTION_NETWORK_MAC, mac)}
            device_info["serial_number"] = coordinator.board_info.serial_board_box
            device_info["sw_version"] = coordinator.board_info.software_version
            if model_id := coordinator.board_info.box_sub_type_name:
                device_info["model_id"] = model_id
        else:
            device_info["via_device"] = (DOMAIN, self._device_identifier(mac, 1))

        self._attr_device_info = device_info

    @staticmethod
    def _device_identifier(mac: str, node_id: int) -> str:
        """Return the stable device identifier used in the registry."""
        return f"{mac}_{node_id}"

    @staticmethod
    def _configuration_url(
        coordinator: DucoCoordinator,
        node: Node,
        is_box: bool,
    ) -> str | None:
        """Return the device configuration URL when it is unambiguous."""
        host = coordinator.config_entry.data[CONF_HOST]

        if is_box:
            return f"http://{host}"

        if (zone_group := coordinator.data.node_zone_groups.get(node.node_id)) is None:
            return None

        zone_id, group_id = zone_group
        return (
            f"http://{host}/nodeconfig.html?node={node.node_id}"
            f"&zone={zone_id}&group={group_id}"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._node_id in self.coordinator.data.nodes

    @property
    def _node(self) -> Node:
        """Return the current node data from the coordinator."""
        return self.coordinator.data.nodes[self._node_id]
