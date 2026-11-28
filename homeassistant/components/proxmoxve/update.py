"""Update platform for Proxmox VE."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aioproxmox.model.pve import OperationalStatus

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ProxmoxPermission
from .coordinator import (
    ProxmoxConfigEntry,
    ProxmoxNodeData,
    ProxmoxNodeSoftware,
    ProxmoxSoftwareCoordinator,
    node_device_info,
    proxmox_node_url,
)
from .helpers import ProxmoxUpdateInfo, update_version

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ProxmoxNodeUpdateEntityDescription(UpdateEntityDescription):
    """Describes Proxmox node update entity."""

    installed_version: Callable[[ProxmoxNodeSoftware], str | None]
    update_info: Callable[[ProxmoxNodeSoftware], ProxmoxUpdateInfo | None]


NODE_UPDATES: tuple[ProxmoxNodeUpdateEntityDescription, ...] = (
    ProxmoxNodeUpdateEntityDescription(
        key="node_update",
        translation_key="node_update",
        entity_category=EntityCategory.CONFIG,
        installed_version=lambda data: data.version.version,
        update_info=lambda data: (
            update_version(data.version.version, data.update)
            if data.update is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Proxmox VE update entities."""
    status_coordinator = entry.runtime_data.status
    software_coordinator = entry.runtime_data.software

    def _async_add_new_nodes(nodes: list[ProxmoxNodeData]) -> None:
        """Add update entities for newly discovered nodes."""
        async_add_entities(
            ProxmoxNodeUpdateEntity(software_coordinator, entity_description, node)
            for node in nodes
            for entity_description in NODE_UPDATES
            if status_coordinator.permissions.has_node_permission(
                node.node.node, ProxmoxPermission.SYSMOD
            )
        )

    status_coordinator.new_nodes_callbacks.append(_async_add_new_nodes)
    _async_add_new_nodes(
        [
            data
            for data in status_coordinator.data.values()
            if data.node.node in status_coordinator.known_nodes
        ]
    )


class ProxmoxNodeUpdateEntity(
    CoordinatorEntity[ProxmoxSoftwareCoordinator], UpdateEntity
):
    """Represents a Proxmox VE node software update."""

    _attr_has_entity_name = True
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    entity_description: ProxmoxNodeUpdateEntityDescription

    def __init__(
        self,
        coordinator: ProxmoxSoftwareCoordinator,
        entity_description: ProxmoxNodeUpdateEntityDescription,
        node_data: ProxmoxNodeData,
    ) -> None:
        """Initialize the Proxmox node update entity."""
        super().__init__(coordinator)
        self.device_name = node_data.node.node
        self.entity_description = entity_description
        self._attr_device_info = node_device_info(coordinator.status, node_data)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}"
            f"_{node_data.node.id}"
            f"_{entity_description.key}"
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Also follow the status coordinator, which tracks if the node is online."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.status.async_add_listener(self._handle_coordinator_update)
        )

    @property
    @override
    def installed_version(self) -> str | None:
        """Return installed version."""
        return self.entity_description.installed_version(
            self.coordinator.data[self.device_name]
        )

    @property
    @override
    def latest_version(self) -> str | None:
        """Return latest version."""
        update_info = self._update_info()
        return update_info.latest_version_id if update_info else None

    @property
    @override
    def has_update(self) -> bool:
        """Return True if package updates are pending."""
        update_info = self._update_info()
        return update_info is not None and update_info.total_updates > 0

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the release summary for the update."""
        url = proxmox_node_url(self.coordinator.status, self.device_name)
        update_info = self._update_info()
        if update_info and update_info.total_updates > 0:
            return f"A total of {update_info.total_updates} package update(s) are pending installation: of these {update_info.proxmox_updates} relate to Proxmox and {update_info.other_updates} to other updates. Please visit the [Proxmox VE node]({url}) for details on the pending updates and to upgrade to {update_info.latest_version}."
        return None

    @property
    @override
    def available(self) -> bool:
        """Return if the update platform is available."""
        return (
            super().available
            and (node_data := self.coordinator.status.data.get(self.device_name))
            is not None
            and node_data.node.status == OperationalStatus.ONLINE
            and self.device_name in self.coordinator.data
            and self._update_info() is not None
        )

    @override
    def release_notes(self) -> str | None:
        """Return the release notes for the update."""
        return self.release_summary

    def _update_info(self) -> ProxmoxUpdateInfo | None:
        """Return update info or None if unavailable."""
        return self.entity_description.update_info(
            self.coordinator.data[self.device_name]
        )
