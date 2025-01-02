"""Platform for Portainer base entity."""

import logging
from typing import TYPE_CHECKING

from aiotainer.model import Container, NodeData, Snapshot

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PortainerDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type PortainerConfigEntry = ConfigEntry[PortainerDataUpdateCoordinator]


class ContainerBaseEntity(CoordinatorEntity[PortainerDataUpdateCoordinator]):
    """Defining the Portainer base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
        container_id: str,
    ) -> None:
        """Initialize PortainerEntity."""
        super().__init__(coordinator)
        self.node_id = node_id
        self.container_id = container_id
        if TYPE_CHECKING:
            assert coordinator.config_entry is not None
        entry: PortainerConfigEntry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(node_id))},
            name=self.node_attributes.name,
            configuration_url=entry.data["url"],
        )

    @property
    def node_attributes(self) -> NodeData:
        """Get the node attributes of the current node."""
        return self.coordinator.data[self.node_id]

    @property
    def snapshot_attributes(self) -> Snapshot:
        """Get latest snapshot attributes."""
        return self.node_attributes.snapshots[-1]

    @property
    def container_attributes(self) -> Container:
        """Get the container attributes of the current container."""
        return self.snapshot_attributes.docker_snapshot_raw.containers[
            self.container_id
        ]
