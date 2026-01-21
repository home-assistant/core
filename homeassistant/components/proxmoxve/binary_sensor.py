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

    async_add_entities(
        ProxmoxNodeBinarySensor(
            coordinator,
            entity_description,
            node_data,
        )
        for entity_description in NODE_SENSORS
        for node_data in coordinator.data.nodes.values()
    )

    async_add_entities(
        ProxmoxVMBinarySensor(
            coordinator,
            entity_description,
            vm_data,
            node_data,
        )
        for node_data in coordinator.data.nodes.values()
        for vm_data in node_data.vms.values()
        for entity_description in VM_SENSORS
    )

    async_add_entities(
        ProxmoxContainerBinarySensor(
            coordinator,
            entity_description,
            container_data,
            node_data,
        )
        for node_data in coordinator.data.nodes.values()
        for container_data in node_data.containers.values()
        for entity_description in CONTAINER_SENSORS
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

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_node_{node_data.node['id']}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.device_name in self.coordinator.data.nodes

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(
            self.coordinator.data.nodes[self.device_name]
        )


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

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._node_name}_vm_{self.device_id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return (
            super().available
            and self._node_name in self.coordinator.data.nodes
            and self.device_id in self.coordinator.data.nodes[self._node_name].vms
        )

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

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._node_name}_container_{self.device_id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return (
            super().available
            and self._node_name in self.coordinator.data.nodes
            and self.device_id
            in self.coordinator.data.nodes[self._node_name].containers
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.container_data)
