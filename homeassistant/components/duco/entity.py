"""Base entity for the Duco integration."""

from typing import cast

from duco_connectivity.models import Node, NodeType
from yarl import URL

from homeassistant.const import CONF_HOST
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
        # Loaded Duco entries always get a stable unique ID from the config flow.
        mac = cast(str, coordinator.config_entry.unique_id)

        self._mac = mac
        self._is_box = node.general.node_type == NodeType.BOX

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_identifier(mac, node.node_id))},
            manufacturer="Duco",
            model=(
                coordinator.board_info.box_name
                if self._is_box
                else node.general.node_type
            ),
            name=(
                (node.general.name or coordinator.board_info.box_name)
                if self._is_box
                else (node.general.name or f"Node {node.node_id}")
            ),
            configuration_url=self._configuration_url(),
        )
        if self._is_box:
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

    def _configuration_url(self) -> str | None:
        """Return the device configuration URL when it is unambiguous."""
        host = self.coordinator.config_entry.data[CONF_HOST]

        if self._is_box:
            return str(URL.build(scheme="http", host=host))

        if (
            zone_group := self.coordinator.data.node_zone_groups.get(self._node_id)
        ) is None:
            return None

        zone_id, group_id = zone_group
        return str(
            URL.build(
                scheme="http",
                host=host,
                path="/nodeconfig.html",
                query=[
                    ("node", str(self._node_id)),
                    ("zone", str(zone_id)),
                    ("group", str(group_id)),
                ],
            )
        )

    def _update_device_registry_configuration_url(self) -> None:
        """Update the device visit link when coordinator data changes."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._device_identifier(self._mac, self._node_id))}
        )
        if device is None:
            return

        configuration_url = self._configuration_url()
        if device.configuration_url == configuration_url:
            return

        # Home Assistant only applies entity device_info during registration.
        device_info = self._attr_device_info
        if device_info is None:
            return

        device_info["configuration_url"] = configuration_url
        device_registry.async_update_device(
            device_id=device.id,
            configuration_url=configuration_url,
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""
        self._update_device_registry_configuration_url()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._node_id in self.coordinator.data.nodes

    @property
    def _node(self) -> Node:
        """Return the current node data from the coordinator."""
        return self.coordinator.data.nodes[self._node_id]
