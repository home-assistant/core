"""Binary sensor to read Proxmox VE data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NODE_ONLINE, VM_CONTAINER_RUNNING
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator, ProxmoxNodeData
from .entity import ProxmoxContainerEntity, ProxmoxNodeEntity, ProxmoxVMEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ProxmoxContainerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Proxmox container binary sensor description."""

    state_fn: Callable[[dict[str, Any]], bool | None]


@dataclass(frozen=True, kw_only=True)
class ProxmoxVMBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Proxmox endpoint binary sensor description."""

    state_fn: Callable[[dict[str, Any]], bool | None]


@dataclass(frozen=True, kw_only=True)
class ProxmoxNodeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Proxmox node binary sensor description."""

    state_fn: Callable[[ProxmoxNodeData], bool | None]


NODE_SENSORS: tuple[ProxmoxNodeBinarySensorEntityDescription, ...] = (
    ProxmoxNodeBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.node["status"] == NODE_ONLINE,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

CONTAINER_SENSORS: tuple[ProxmoxContainerBinarySensorEntityDescription, ...] = (
    ProxmoxContainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data["status"] == VM_CONTAINER_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

VM_SENSORS: tuple[ProxmoxVMBinarySensorEntityDescription, ...] = (
    ProxmoxVMBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data["status"] == VM_CONTAINER_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Proxmox VE binary sensors."""
    coordinator = entry.runtime_data

    def _async_add_new_nodes(nodes: list[ProxmoxNodeData]) -> None:
        """Add new node binary sensors."""
        async_add_entities(
            ProxmoxNodeBinarySensor(coordinator, entity_description, node)
            for node in nodes
            for entity_description in NODE_SENSORS
        )

    def _async_add_new_vms(
        vms: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new VM binary sensors."""
        async_add_entities(
            ProxmoxVMBinarySensor(coordinator, entity_description, vm, node_data)
            for (node_data, vm) in vms
            for entity_description in VM_SENSORS
        )

    def _async_add_new_containers(
        containers: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new container binary sensors."""
        async_add_entities(
            ProxmoxContainerBinarySensor(
                coordinator, entity_description, container, node_data
            )
            for (node_data, container) in containers
            for entity_description in CONTAINER_SENSORS
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


class ProxmoxNodeBinarySensor(ProxmoxNodeEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE node data."""

    entity_description: ProxmoxNodeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        entity_description: ProxmoxNodeBinarySensorEntityDescription,
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize Proxmox node binary sensor entity."""
        self.entity_description = entity_description
        super().__init__(coordinator, node_data)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{node_data.node['id']}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.coordinator.data[self.device_name])


class ProxmoxVMBinarySensor(ProxmoxVMEntity, BinarySensorEntity):
    """Representation of a Proxmox VM binary sensor."""

    entity_description: ProxmoxVMBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        entity_description: ProxmoxVMBinarySensorEntityDescription,
        vm_data: dict[str, Any],
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox VM binary sensor."""
        self.entity_description = entity_description
        super().__init__(coordinator, vm_data, node_data)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.vm_data)


class ProxmoxContainerBinarySensor(ProxmoxContainerEntity, BinarySensorEntity):
    """Representation of a Proxmox Container binary sensor."""

    entity_description: ProxmoxContainerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        entity_description: ProxmoxContainerBinarySensorEntityDescription,
        container_data: dict[str, Any],
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox Container binary sensor."""
        self.entity_description = entity_description
        super().__init__(coordinator, container_data, node_data)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.container_data)
