"""Update platform for Proxmox VE."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ProxmoxConfigEntry, ProxmoxNodeData
from .entity import ProxmoxNodeEntity
from .helpers import ProxmoxUpdateInfo, update_version

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ProxmoxNodeUpdateEntityDescription(UpdateEntityDescription):
    """Describes Proxmox node update entity."""

    installed_version: Callable[[ProxmoxNodeData], str]
    update_info: Callable[[ProxmoxNodeData], ProxmoxUpdateInfo]


NODE_UPDATES: tuple[ProxmoxNodeUpdateEntityDescription, ...] = (
    ProxmoxNodeUpdateEntityDescription(
        key="node_update",
        translation_key="node_update",
        entity_category=EntityCategory.CONFIG,
        installed_version=lambda node_data: node_data.version.get("version", "unknown"),
        update_info=lambda node_data: update_version(
            node_data.version.get("version", "unknown"),
            node_data.update if isinstance(node_data.update, list) else [],
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Proxmox VE update entities."""
    coordinator = entry.runtime_data

    def _async_add_new_nodes(nodes: list[ProxmoxNodeData]) -> None:
        """Add update entities for newly discovered nodes."""
        async_add_entities(
            ProxmoxNodeUpdateEntity(coordinator, entity_description, node)
            for node in nodes
            for entity_description in NODE_UPDATES
        )

    coordinator.new_nodes_callbacks.append(_async_add_new_nodes)
    _async_add_new_nodes(
        [
            node_data
            for node_data in coordinator.data.values()
            if node_data.node["node"] in coordinator.known_nodes
        ]
    )


class ProxmoxNodeUpdateEntity(ProxmoxNodeEntity, UpdateEntity):
    """Represents a Proxmox VE node software update."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    entity_description: ProxmoxNodeUpdateEntityDescription

    @property
    def installed_version(self) -> str | None:
        """Return installed version."""
        return self.entity_description.installed_version(
            self.coordinator.data[self.device_name]
        )

    @property
    def latest_version(self) -> str | None:
        """Return latest version."""
        return self.entity_description.update_info(
            self.coordinator.data[self.device_name]
        ).latest_version_id

    @property
    def release_summary(self) -> str | None:
        """Return the release summary for the update."""
        update_info = self.entity_description.update_info(
            self.coordinator.data[self.device_name]
        )
        return f"A total of {update_info.total_updates} update(s) is/are pending installation. There is/are {update_info.proxmox_updates} Proxmox VE update(s) and {update_info.other_updates} other update(s) pending. If you run the update, all pending updates will be installed. Proxmox will be updated to version {update_info.latest_version}. Please check the Proxmox VE node for details on the pending updates."
