"""Button platform for Proxmox VE."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import requests
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator, ProxmoxNodeData
from .entity import ProxmoxContainerEntity, ProxmoxNodeEntity, ProxmoxVMEntity
from .helpers import is_granted


@dataclass(frozen=True, kw_only=True)
class ProxmoxNodeButtonNodeEntityDescription(ButtonEntityDescription):
    """Class to hold Proxmox node button description."""

    press_action: Callable[[ProxmoxCoordinator, str], None]


@dataclass(frozen=True, kw_only=True)
class ProxmoxVMButtonEntityDescription(ButtonEntityDescription):
    """Class to hold Proxmox VM button description."""

    press_action: Callable[[ProxmoxCoordinator, str, int], None]


@dataclass(frozen=True, kw_only=True)
class ProxmoxContainerButtonEntityDescription(ButtonEntityDescription):
    """Class to hold Proxmox container button description."""

    press_action: Callable[[ProxmoxCoordinator, str, int], None]


NODE_BUTTONS: tuple[ProxmoxNodeButtonNodeEntityDescription, ...] = (
    ProxmoxNodeButtonNodeEntityDescription(
        key="reboot",
        press_action=lambda coordinator, node: coordinator.proxmox.nodes(
            node
        ).status.post(command="reboot"),
        entity_category=EntityCategory.CONFIG,
        device_class=ButtonDeviceClass.RESTART,
    ),
    ProxmoxNodeButtonNodeEntityDescription(
        key="shutdown",
        translation_key="shutdown",
        press_action=lambda coordinator, node: coordinator.proxmox.nodes(
            node
        ).status.post(command="shutdown"),
        entity_category=EntityCategory.CONFIG,
    ),
    ProxmoxNodeButtonNodeEntityDescription(
        key="start_all",
        translation_key="start_all",
        press_action=lambda coordinator, node: coordinator.proxmox.nodes(
            node
        ).startall.post(),
        entity_category=EntityCategory.CONFIG,
    ),
    ProxmoxNodeButtonNodeEntityDescription(
        key="stop_all",
        translation_key="stop_all",
        press_action=lambda coordinator, node: coordinator.proxmox.nodes(
            node
        ).stopall.post(),
        entity_category=EntityCategory.CONFIG,
    ),
)

VM_BUTTONS: tuple[ProxmoxVMButtonEntityDescription, ...] = (
    ProxmoxVMButtonEntityDescription(
        key="start",
        translation_key="start",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).qemu(vmid).status.start.post()
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    ProxmoxVMButtonEntityDescription(
        key="stop",
        translation_key="stop",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).qemu(vmid).status.stop.post()
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    ProxmoxVMButtonEntityDescription(
        key="restart",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).qemu(vmid).status.reboot.post()
        ),
        entity_category=EntityCategory.CONFIG,
        device_class=ButtonDeviceClass.RESTART,
    ),
    ProxmoxVMButtonEntityDescription(
        key="hibernate",
        translation_key="hibernate",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).qemu(vmid).status.hibernate.post()
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    ProxmoxVMButtonEntityDescription(
        key="reset",
        translation_key="reset",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).qemu(vmid).status.reset.post()
        ),
        entity_category=EntityCategory.CONFIG,
    ),
)

CONTAINER_BUTTONS: tuple[ProxmoxContainerButtonEntityDescription, ...] = (
    ProxmoxContainerButtonEntityDescription(
        key="start",
        translation_key="start",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).lxc(vmid).status.start.post()
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    ProxmoxContainerButtonEntityDescription(
        key="stop",
        translation_key="stop",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).lxc(vmid).status.stop.post()
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    ProxmoxContainerButtonEntityDescription(
        key="restart",
        press_action=lambda coordinator, node, vmid: (
            coordinator.proxmox.nodes(node).lxc(vmid).status.reboot.post()
        ),
        entity_category=EntityCategory.CONFIG,
        device_class=ButtonDeviceClass.RESTART,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ProxmoxVE buttons."""
    coordinator = entry.runtime_data

    def _async_add_new_nodes(nodes: list[ProxmoxNodeData]) -> None:
        """Add new node buttons."""
        async_add_entities(
            ProxmoxNodeButtonEntity(coordinator, entity_description, node)
            for node in nodes
            for entity_description in NODE_BUTTONS
        )

    def _async_add_new_vms(
        vms: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new VM buttons."""
        async_add_entities(
            ProxmoxVMButtonEntity(coordinator, entity_description, vm, node_data)
            for (node_data, vm) in vms
            for entity_description in VM_BUTTONS
        )

    def _async_add_new_containers(
        containers: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new container buttons."""
        async_add_entities(
            ProxmoxContainerButtonEntity(
                coordinator, entity_description, container, node_data
            )
            for (node_data, container) in containers
            for entity_description in CONTAINER_BUTTONS
        )

    coordinator.new_nodes_callbacks.append(_async_add_new_nodes)
    coordinator.new_vms_callbacks.append(_async_add_new_vms)
    coordinator.new_containers_callbacks.append(_async_add_new_containers)

    _async_add_new_nodes(
        [
            node_data
            for node_data in coordinator.data.values()
            if node_data.node["node"] in coordinator.known_nodes
        ]
    )
    _async_add_new_vms(
        [
            (node_data, vm_data)
            for node_data in coordinator.data.values()
            for vmid, vm_data in node_data.vms.items()
            if (node_data.node["node"], vmid) in coordinator.known_vms
        ]
    )
    _async_add_new_containers(
        [
            (node_data, container_data)
            for node_data in coordinator.data.values()
            for vmid, container_data in node_data.containers.items()
            if (node_data.node["node"], vmid) in coordinator.known_containers
        ]
    )


class ProxmoxBaseButton(ButtonEntity):
    """Common base for Proxmox buttons. Basically to ensure the async_press logic isn't duplicated."""

    entity_description: ButtonEntityDescription
    coordinator: ProxmoxCoordinator

    @abstractmethod
    async def _async_press_call(self) -> None:
        """Abstract method used per Proxmox button class."""

    async def async_press(self) -> None:
        """Trigger the Proxmox button press service."""
        try:
            await self._async_press_call()
        except AuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_no_details",
            ) from err
        except SSLError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth_no_details",
            ) from err
        except ConnectTimeout as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_connect_no_details",
            ) from err
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error_no_details",
            ) from err


class ProxmoxNodeButtonEntity(ProxmoxNodeEntity, ProxmoxBaseButton):
    """Represents a Proxmox Node button entity."""

    entity_description: ProxmoxNodeButtonNodeEntityDescription

    async def _async_press_call(self) -> None:
        """Execute the node button action via executor."""
        if not is_granted(self.coordinator.permissions, p_type="nodes"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_permission_node_power",
            )
        await self.hass.async_add_executor_job(
            self.entity_description.press_action,
            self.coordinator,
            self._node_data.node["node"],
        )


class ProxmoxVMButtonEntity(ProxmoxVMEntity, ProxmoxBaseButton):
    """Represents a Proxmox VM button entity."""

    entity_description: ProxmoxVMButtonEntityDescription

    async def _async_press_call(self) -> None:
        """Execute the VM button action via executor."""
        if not is_granted(self.coordinator.permissions, p_type="vms"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_permission_vm_lxc_power",
            )
        await self.hass.async_add_executor_job(
            self.entity_description.press_action,
            self.coordinator,
            self._node_name,
            self.vm_data["vmid"],
        )


class ProxmoxContainerButtonEntity(ProxmoxContainerEntity, ProxmoxBaseButton):
    """Represents a Proxmox Container button entity."""

    entity_description: ProxmoxContainerButtonEntityDescription

    async def _async_press_call(self) -> None:
        """Execute the container button action via executor."""
        # Container power actions fall under vms
        if not is_granted(self.coordinator.permissions, p_type="vms"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_permission_vm_lxc_power",
            )
        await self.hass.async_add_executor_job(
            self.entity_description.press_action,
            self.coordinator,
            self._node_name,
            self.container_data["vmid"],
        )
