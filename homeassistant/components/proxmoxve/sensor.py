"""Sensor platform for Proxmox VE integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ProxmoxConfigEntry, ProxmoxNodeData
from .entity import (
    ProxmoxContainerEntity,
    ProxmoxNodeEntity,
    ProxmoxStorageEntity,
    ProxmoxVMEntity,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ProxmoxNodeSensorEntityDescription(SensorEntityDescription):
    """Class to hold Proxmox node sensor description."""

    value_fn: Callable[[ProxmoxNodeData], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class ProxmoxVMSensorEntityDescription(SensorEntityDescription):
    """Class to hold Proxmox VM sensor description."""

    value_fn: Callable[[dict[str, Any]], StateType]


@dataclass(frozen=True, kw_only=True)
class ProxmoxContainerSensorEntityDescription(SensorEntityDescription):
    """Class to hold Proxmox container sensor description."""

    value_fn: Callable[[dict[str, Any]], StateType]


@dataclass(frozen=True, kw_only=True)
class ProxmoxStorageSensorEntityDescription(SensorEntityDescription):
    """Class to hold Proxmox storage sensor description."""

    value_fn: Callable[[dict[str, Any]], StateType]


NODE_SENSORS: tuple[ProxmoxNodeSensorEntityDescription, ...] = (
    ProxmoxNodeSensorEntityDescription(
        key="node_cpu",
        translation_key="node_cpu",
        value_fn=lambda data: data.node["cpu"] * 100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_max_cpu",
        translation_key="node_max_cpu",
        value_fn=lambda data: data.node["maxcpu"],
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_disk",
        translation_key="node_disk",
        value_fn=lambda data: data.node["disk"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_max_disk",
        translation_key="node_max_disk",
        value_fn=lambda data: data.node["maxdisk"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_memory",
        translation_key="node_memory",
        value_fn=lambda data: data.node["mem"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_max_memory",
        translation_key="node_max_memory",
        value_fn=lambda data: data.node["maxmem"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_memory_percentage",
        translation_key="node_memory_percentage",
        value_fn=lambda data: int(data.node["mem"]) / int(data.node["maxmem"]) * 100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_uptime",
        translation_key="node_uptime",
        value_fn=lambda data: data.node["uptime"],
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_status",
        translation_key="node_status",
        value_fn=lambda data: data.node["status"],
        device_class=SensorDeviceClass.ENUM,
        options=["online", "offline"],
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_backup_last_backup",
        translation_key="node_backup_last_backup",
        value_fn=lambda data: (
            dt_util.utc_from_timestamp(data.backups[0]["endtime"])
            if data.backups
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ProxmoxNodeSensorEntityDescription(
        key="node_backup_duration",
        translation_key="node_backup_duration",
        value_fn=lambda data: (
            data.backups[0]["endtime"] - data.backups[0]["starttime"]
            if data.backups
            else None
        ),
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

VM_SENSORS: tuple[ProxmoxVMSensorEntityDescription, ...] = (
    ProxmoxVMSensorEntityDescription(
        key="vm_max_cpu",
        translation_key="vm_max_cpu",
        value_fn=lambda data: data["cpus"],
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_cpu",
        translation_key="vm_cpu",
        value_fn=lambda data: data["cpu"] * 100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_memory",
        translation_key="vm_memory",
        value_fn=lambda data: data["mem"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_max_memory",
        translation_key="vm_max_memory",
        value_fn=lambda data: data["maxmem"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_memory_percentage",
        translation_key="vm_memory_percentage",
        value_fn=lambda data: int(data["mem"]) / int(data["maxmem"]) * 100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_uptime",
        translation_key="vm_uptime",
        value_fn=lambda data: data["uptime"],
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_disk",
        translation_key="vm_disk",
        value_fn=lambda data: data["disk"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_max_disk",
        translation_key="vm_max_disk",
        value_fn=lambda data: data["maxdisk"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_status",
        translation_key="vm_status",
        value_fn=lambda data: data["status"],
        device_class=SensorDeviceClass.ENUM,
        options=["running", "stopped", "suspended"],
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_netin",
        translation_key="vm_netin",
        value_fn=lambda data: data["netin"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ProxmoxVMSensorEntityDescription(
        key="vm_netout",
        translation_key="vm_netout",
        value_fn=lambda data: data["netout"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

CONTAINER_SENSORS: tuple[ProxmoxContainerSensorEntityDescription, ...] = (
    ProxmoxContainerSensorEntityDescription(
        key="container_max_cpu",
        translation_key="container_max_cpu",
        value_fn=lambda data: data["cpus"],
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_cpu",
        translation_key="container_cpu",
        value_fn=lambda data: data["cpu"] * 100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_memory",
        translation_key="container_memory",
        value_fn=lambda data: data["mem"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_max_memory",
        translation_key="container_max_memory",
        value_fn=lambda data: data["maxmem"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_memory_percentage",
        translation_key="container_memory_percentage",
        value_fn=lambda data: int(data["mem"]) / int(data["maxmem"]) * 100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_uptime",
        translation_key="container_uptime",
        value_fn=lambda data: data["uptime"],
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_disk",
        translation_key="container_disk",
        value_fn=lambda data: data["disk"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_max_disk",
        translation_key="container_max_disk",
        value_fn=lambda data: data["maxdisk"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_status",
        translation_key="container_status",
        value_fn=lambda data: data["status"],
        device_class=SensorDeviceClass.ENUM,
        options=["running", "stopped", "suspended"],
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_netin",
        translation_key="container_netin",
        value_fn=lambda data: data["netin"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ProxmoxContainerSensorEntityDescription(
        key="container_netout",
        translation_key="container_netout",
        value_fn=lambda data: data["netout"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

STORAGE_SENSORS: tuple[ProxmoxStorageSensorEntityDescription, ...] = (
    ProxmoxStorageSensorEntityDescription(
        key="storage_used",
        translation_key="storage_used",
        value_fn=lambda data: data["used"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxStorageSensorEntityDescription(
        key="storage_total",
        translation_key="storage_total",
        value_fn=lambda data: data["total"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxStorageSensorEntityDescription(
        key="storage_available",
        translation_key="storage_available",
        value_fn=lambda data: data["avail"],
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ProxmoxStorageSensorEntityDescription(
        key="storage_used_percentage",
        translation_key="storage_used_percentage",
        value_fn=lambda data: round(data["used_fraction"] * 100, 1),
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Proxmox VE sensors."""
    coordinator = entry.runtime_data

    def _async_add_new_nodes(nodes: list[ProxmoxNodeData]) -> None:
        """Add new node sensors."""
        async_add_entities(
            ProxmoxNodeSensor(coordinator, entity_description, node)
            for node in nodes
            for entity_description in NODE_SENSORS
        )

    def _async_add_new_vms(
        vms: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new VM sensors."""
        async_add_entities(
            ProxmoxVMSensor(coordinator, entity_description, vm, node_data)
            for (node_data, vm) in vms
            for entity_description in VM_SENSORS
        )

    def _async_add_new_containers(
        containers: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new container sensors."""
        async_add_entities(
            ProxmoxContainerSensor(
                coordinator, entity_description, container, node_data
            )
            for (node_data, container) in containers
            for entity_description in CONTAINER_SENSORS
        )

    def _async_add_new_storages(
        storages: list[tuple[ProxmoxNodeData, dict[str, Any]]],
    ) -> None:
        """Add new storage sensors."""
        async_add_entities(
            ProxmoxStorageSensor(coordinator, entity_description, storage, node_data)
            for (node_data, storage) in storages
            for entity_description in STORAGE_SENSORS
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
            for storage_name, storage_data in node_data.storages.items()
            if (node_data.node["node"], storage_name) in coordinator.known_storages
        ]
    )


class ProxmoxNodeSensor(ProxmoxNodeEntity, SensorEntity):
    """Representation of a Proxmox VE node sensor."""

    entity_description: ProxmoxNodeSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self.device_name])


class ProxmoxVMSensor(ProxmoxVMEntity, SensorEntity):
    """Represents a Proxmox VE VM sensor."""

    entity_description: ProxmoxVMSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.vm_data)


class ProxmoxContainerSensor(ProxmoxContainerEntity, SensorEntity):
    """Represents a Proxmox VE container sensor."""

    entity_description: ProxmoxContainerSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.container_data)


class ProxmoxStorageSensor(ProxmoxStorageEntity, SensorEntity):
    """Represents a Proxmox VE storage sensor."""

    entity_description: ProxmoxStorageSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.storage_data)
