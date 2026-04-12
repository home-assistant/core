"""Binary sensor to read Proxmox VE data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    NODE_ONLINE,
    STATUS_OK,
    STORAGE_ACTIVE,
    STORAGE_ENABLED,
    STORAGE_SHARED,
    VM_CONTAINER_RUNNING,
)
from .coordinator import ProxmoxConfigEntry, ProxmoxNodeData
from .entity import (
    ProxmoxContainerEntity,
    ProxmoxNodeEntity,
    ProxmoxStorageEntity,
    ProxmoxVMEntity,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ProxmoxContainerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Proxmox container binary sensor description."""

    state_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class ProxmoxVMBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Proxmox endpoint binary sensor description."""

    state_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class ProxmoxNodeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Proxmox node binary sensor description."""

    state_fn: Callable[[ProxmoxNodeData], bool | None]
    exists_fn: Callable[[ProxmoxNodeData], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class ProxmoxStorageBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Proxmox storage binary sensor description."""

    state_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda _: True


NODE_SENSORS: tuple[ProxmoxNodeBinarySensorEntityDescription, ...] = (
    ProxmoxNodeBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.node.get("status") == NODE_ONLINE,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ProxmoxNodeBinarySensorEntityDescription(
        key="node_backup_status",
        translation_key="node_backup_status",
        state_fn=lambda data: (
            status != STATUS_OK
            if data.backups and (status := data.backups[0].get("status")) is not None
            else None
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

CONTAINER_SENSORS: tuple[ProxmoxContainerBinarySensorEntityDescription, ...] = (
    ProxmoxContainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.get("status") == VM_CONTAINER_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

VM_SENSORS: tuple[ProxmoxVMBinarySensorEntityDescription, ...] = (
    ProxmoxVMBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.get("status") == VM_CONTAINER_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

STORAGE_SENSORS: tuple[ProxmoxStorageBinarySensorEntityDescription, ...] = (
    ProxmoxStorageBinarySensorEntityDescription(
        key="storage_active",
        translation_key="storage_active",
        state_fn=lambda data: data.get("active") == STORAGE_ACTIVE,
        exists_fn=lambda data: "active" in data,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ProxmoxStorageBinarySensorEntityDescription(
        key="storage_enabled",
        translation_key="storage_enabled",
        state_fn=lambda data: data.get("enabled") == STORAGE_ENABLED,
        exists_fn=lambda data: "enabled" in data,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ProxmoxStorageBinarySensorEntityDescription(
        key="storage_shared",
        translation_key="storage_shared",
        state_fn=lambda data: data.get("shared") == STORAGE_SHARED,
        exists_fn=lambda data: "shared" in data,
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
            if entity_description.exists_fn(node)
        )

    def _async_add_new_vms(
        vms: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new VM binary sensors."""
        async_add_entities(
            ProxmoxVMBinarySensor(coordinator, entity_description, vm, node_data)
            for (node_data, vm) in vms
            for entity_description in VM_SENSORS
            if entity_description.exists_fn(vm)
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
            if entity_description.exists_fn(container)
        )

    def _async_add_new_storages(
        storages: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new storage binary sensors."""
        async_add_entities(
            ProxmoxStorageBinarySensor(
                coordinator, entity_description, storage, node_data
            )
            for (node_data, storage) in storages
            for entity_description in STORAGE_SENSORS
            if entity_description.exists_fn(storage)
        )

    coordinator.new_nodes_callbacks.append(_async_add_new_nodes)
    coordinator.new_vms_callbacks.append(_async_add_new_vms)
    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    coordinator.new_storages_callbacks.append(_async_add_new_storages)

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
    _async_add_new_storages(
        [
            (node_data, storage_data)
            for node_data in coordinator.data.values()
            for storage_id, storage_data in node_data.storages.items()
            if (node_data.node["node"], storage_id) in coordinator.known_storages
        ]
    )


class ProxmoxNodeBinarySensor(ProxmoxNodeEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE node data."""

    entity_description: ProxmoxNodeBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.coordinator.data[self.device_name])


class ProxmoxVMBinarySensor(ProxmoxVMEntity, BinarySensorEntity):
    """Representation of a Proxmox VM binary sensor."""

    entity_description: ProxmoxVMBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.vm_data)


class ProxmoxContainerBinarySensor(ProxmoxContainerEntity, BinarySensorEntity):
    """Representation of a Proxmox Container binary sensor."""

    entity_description: ProxmoxContainerBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.container_data)


class ProxmoxStorageBinarySensor(ProxmoxStorageEntity, BinarySensorEntity):
    """Representation of a Proxmox Storage binary sensor."""

    entity_description: ProxmoxStorageBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.storage_data)
