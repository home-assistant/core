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
    update_info: Callable[[ProxmoxNodeData], ProxmoxUpdateInfo | bool]


NODE_UPDATES: tuple[ProxmoxNodeUpdateEntityDescription, ...] = (
    ProxmoxNodeUpdateEntityDescription(
        key="node_update",
        translation_key="node_update",
        entity_category=EntityCategory.CONFIG,
        installed_version=lambda node_data: node_data.version.get("version", "unknown"),
        update_info=lambda node_data: update_version(
            node_data.version.get("version", "unknown"),
            node_data.update,
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
        update_info = self._update_info()
        return update_info.latest_version_id if update_info else None

    @property
    def release_summary(self) -> str | None:
        """Return the release summary for the update."""
        url = self.device_info.get("configuration_url") if self.device_info else None
        update_info = self._update_info()
        if update_info:
            return f"A total of {update_info.total_updates} package update(s) are pending installation: of these {update_info.proxmox_updates} relate to Proxmox and {update_info.other_updates} to other updates. Please visit the [Proxmox VE node]({url}) for details on the pending updates and to upgrade to {update_info.latest_version}."
        return None

    @property
    def available(self) -> bool:
        """Return if the update platform is available."""
        return self._update_info() is not None

    def release_notes(self) -> str | None:
        """Return the release notes for the update."""
        return self.release_summary

    def _update_info(self) -> ProxmoxUpdateInfo | None:
        """Return update info or None if unavailable."""
        info = self.entity_description.update_info(
            self.coordinator.data[self.device_name]
        )
        return info if isinstance(info, ProxmoxUpdateInfo) else None
