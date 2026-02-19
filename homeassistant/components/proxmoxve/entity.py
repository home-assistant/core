"""Proxmox parent entity class."""

from __future__ import annotations

from typing import Any

from yarl import URL

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ProxmoxCoordinator, ProxmoxNodeData


def _proxmox_base_url(coordinator: ProxmoxCoordinator) -> URL:
    """Return the base URL for the Proxmox VE."""
    data = coordinator.config_entry.data
    return URL.build(
        scheme="https",
        host=data[CONF_HOST],
        port=data[CONF_PORT],
    )


class ProxmoxCoordinatorEntity(CoordinatorEntity[ProxmoxCoordinator]):
    """Base class for Proxmox entities."""

    _attr_has_entity_name = True


class ProxmoxNodeEntity(ProxmoxCoordinatorEntity):
    """Represents any entity created for a Proxmox VE node."""

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox node entity."""
        super().__init__(coordinator)
        self._node_data = node_data
        self.device_id = node_data.node["id"]
        self.device_name = node_data.node["node"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_node_{self.device_id}")
            },
            name=node_data.node.get("node", str(self.device_id)),
            model="Node",
            configuration_url=_proxmox_base_url(coordinator).with_fragment(
                f"v1:0:=node/{node_data.node['node']}"
            ),
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.device_name in self.coordinator.data


class ProxmoxVMEntity(ProxmoxCoordinatorEntity):
    """Represents a VM entity."""

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        vm_data: dict[str, Any],
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox VM entity."""
        super().__init__(coordinator)
        self._vm_data = vm_data
        self._node_name = node_data.node["node"]
        self.device_id = vm_data["vmid"]
        self.device_name = vm_data["name"]

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_vm_{self.device_id}")
            },
            name=self.device_name,
            model="VM",
            configuration_url=_proxmox_base_url(coordinator).with_fragment(
                f"v1:0:=qemu/{vm_data['vmid']}"
            ),
            via_device=(
                DOMAIN,
                f"{coordinator.config_entry.entry_id}_node_{node_data.node['id']}",
            ),
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return (
            super().available
            and self._node_name in self.coordinator.data
            and self.device_id in self.coordinator.data[self._node_name].vms
        )

    @property
    def vm_data(self) -> dict[str, Any]:
        """Return the VM data."""
        return self.coordinator.data[self._node_name].vms[self.device_id]


class ProxmoxContainerEntity(ProxmoxCoordinatorEntity):
    """Represents a Container entity."""

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        container_data: dict[str, Any],
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox Container entity."""
        super().__init__(coordinator)
        self._container_data = container_data
        self._node_name = node_data.node["node"]
        self.device_id = container_data["vmid"]
        self.device_name = container_data["name"]

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}_container_{self.device_id}",
                )
            },
            name=self.device_name,
            model="Container",
            configuration_url=_proxmox_base_url(coordinator).with_fragment(
                f"v1:0:=lxc/{container_data['vmid']}"
            ),
            via_device=(
                DOMAIN,
                f"{coordinator.config_entry.entry_id}_node_{node_data.node['id']}",
            ),
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return (
            super().available
            and self._node_name in self.coordinator.data
            and self.device_id in self.coordinator.data[self._node_name].containers
        )

    @property
    def container_data(self) -> dict[str, Any]:
        """Return the Container data."""
        return self.coordinator.data[self._node_name].containers[self.device_id]
