"""Platform for Portainer base entity."""

import logging

from aiotainer.model import Container, NodeData, Snapshot

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PortainerDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SnapshotBaseEntity(CoordinatorEntity[PortainerDataUpdateCoordinator]):
    """Defining the Portainer base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
    ) -> None:
        """Initialize PortainerEntity."""
        super().__init__(coordinator)
        self.node_id = node_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(node_id))},
            name=self.node_attributes.name,
        )

    @property
    def node_attributes(self) -> NodeData:
        """Get the node attributes of the current node."""
        return self.coordinator.data[self.node_id]

    @property
    def snapshot_attributes(self) -> Snapshot | None:
        """Get the node attributes of the current node."""
        for node_id in self.coordinator.data:
            for snapshot in self.coordinator.data[node_id].snapshots:
                return snapshot
        return None

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available


class ContainerBaseEntity(SnapshotBaseEntity):
    """Defining the Portainer base Entity."""

    def __init__(
        self,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
        container_id: str,
    ) -> None:
        """Initialize PortainerEntity."""
        super().__init__(coordinator, node_id)
        self.node_id = node_id
        self.container_id = container_id

    @property
    def container_attributes(self) -> Container:
        """Get the node attributes of the current node."""
        return (
            self.coordinator.data[self.node_id]
            .snapshots[-1]
            .docker_snapshot_raw.containers[self.container_id]
        )
