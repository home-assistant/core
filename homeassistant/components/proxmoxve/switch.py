"""Switch platform for Proxmox VE integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, VM_CONTAINER_RUNNING
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator, ProxmoxNodeData
from .entity import ProxmoxContainerEntity, ProxmoxVMEntity


@dataclass(frozen=True, kw_only=True)
class ProxmoxVMSwitchEntityDescription(SwitchEntityDescription):
    """Class to hold Proxmox VM switch description."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]
    turn_on_fn: Callable[[ProxmoxCoordinator, str, int], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[ProxmoxCoordinator, str, int], Coroutine[Any, Any, None]]


@dataclass(frozen=True, kw_only=True)
class ProxmoxContainerSwitchEntityDescription(SwitchEntityDescription):
    """Class to hold Proxmox container switch description."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]
    turn_on_fn: Callable[[ProxmoxCoordinator, str, int], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[ProxmoxCoordinator, str, int], Coroutine[Any, Any, None]]


def proxmox_errors(func) -> Callable[..., Coroutine[Any, Any, None]]:
    """Decorator to handle common Proxmox API errors."""

    async def wrapper(*args: Any, **kwargs: Any) -> None:
        """Wrap wrap, around it."""
        try:
            return await func(*args, **kwargs)
        except AuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth_no_details",
            ) from err
        except SSLError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ssl_error_no_details",
            ) from err
        except ConnectTimeout as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_connect_no_details",
            ) from err
        except ResourceException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_nodes_found",
            ) from err

    return wrapper


@proxmox_errors
async def perform_vm_start(
    coordinator: ProxmoxCoordinator, node_name: str, vmid: int
) -> None:
    """Start a Proxmox VM."""
    await coordinator.hass.async_add_executor_job(
        coordinator.proxmox.nodes(node_name).qemu(vmid).status.start.post
    )


@proxmox_errors
async def perform_vm_stop(
    coordinator: ProxmoxCoordinator, node_name: str, vmid: int
) -> None:
    """Stop a Proxmox VM."""
    await coordinator.hass.async_add_executor_job(
        coordinator.proxmox.nodes(node_name).qemu(vmid).status.stop.post
    )


@proxmox_errors
async def perform_container_start(
    coordinator: ProxmoxCoordinator, node_name: str, vmid: int
) -> None:
    """Start a Proxmox LXC container."""
    await coordinator.hass.async_add_executor_job(
        coordinator.proxmox.nodes(node_name).lxc(vmid).status.start.post
    )


@proxmox_errors
async def perform_container_stop(
    coordinator: ProxmoxCoordinator, node_name: str, vmid: int
) -> None:
    """Stop a Proxmox LXC container."""
    await coordinator.hass.async_add_executor_job(
        coordinator.proxmox.nodes(node_name).lxc(vmid).status.stop.post
    )


VM_SWITCHES: tuple[ProxmoxVMSwitchEntityDescription, ...] = (
    ProxmoxVMSwitchEntityDescription(
        key="vm",
        translation_key="vm",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data["status"] == VM_CONTAINER_RUNNING,
        turn_on_fn=perform_vm_start,
        turn_off_fn=perform_vm_stop,
    ),
)

CONTAINER_SWITCHES: tuple[ProxmoxContainerSwitchEntityDescription, ...] = (
    ProxmoxContainerSwitchEntityDescription(
        key="container",
        translation_key="container",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data["status"] == VM_CONTAINER_RUNNING,
        turn_on_fn=perform_container_start,
        turn_off_fn=perform_container_stop,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Proxmox VE switch entities."""
    coordinator = entry.runtime_data

    def _async_add_new_vms(
        vms: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new VM switch entities."""
        async_add_entities(
            ProxmoxVMSwitch(coordinator, entity_description, vm, node_data)
            for (node_data, vm) in vms
            for entity_description in VM_SWITCHES
        )

    def _async_add_new_containers(
        containers: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new container switch entities."""
        async_add_entities(
            ProxmoxContainerSwitch(
                coordinator, entity_description, container, node_data
            )
            for (node_data, container) in containers
            for entity_description in CONTAINER_SWITCHES
        )

    coordinator.new_vms_callbacks.append(_async_add_new_vms)
    coordinator.new_containers_callbacks.append(_async_add_new_containers)

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


class ProxmoxVMSwitch(ProxmoxVMEntity, SwitchEntity):
    """Representation of a Proxmox VM switch."""

    entity_description: ProxmoxVMSwitchEntityDescription

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        entity_description: ProxmoxVMSwitchEntityDescription,
        vm_data: dict[str, Any],
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox VM switch."""
        self.entity_description = entity_description
        super().__init__(coordinator, vm_data, node_data)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the VM."""
        return self.entity_description.is_on_fn(self.vm_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start (turn on) the VM."""
        await self.entity_description.turn_on_fn(
            self.coordinator,
            self._node_name,
            self.device_id,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop (turn off) the VM."""
        await self.entity_description.turn_off_fn(
            self.coordinator,
            self._node_name,
            self.device_id,
        )
        await self.coordinator.async_request_refresh()


class ProxmoxContainerSwitch(ProxmoxContainerEntity, SwitchEntity):
    """Representation of a Proxmox container switch."""

    entity_description: ProxmoxContainerSwitchEntityDescription

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        entity_description: ProxmoxContainerSwitchEntityDescription,
        container_data: dict[str, Any],
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox container switch."""
        self.entity_description = entity_description
        super().__init__(coordinator, container_data, node_data)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the container."""
        return self.entity_description.is_on_fn(self.container_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start (turn on) the container."""
        await self.entity_description.turn_on_fn(
            self.coordinator,
            self._node_name,
            self.device_id,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop (turn off) the container."""
        await self.entity_description.turn_off_fn(
            self.coordinator,
            self._node_name,
            self.device_id,
        )
        await self.coordinator.async_request_refresh()
