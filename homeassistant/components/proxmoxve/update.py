"""Update platform for Proxmox VE integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import asyncssh

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ProxmoxConfigEntry, ProxmoxNodeData
from .entity import ProxmoxNodeEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ProxmoxNodeUpdateEntityDescription(UpdateEntityDescription):
    """Describes Proxmox node update entity."""

    installed_version: Callable[[ProxmoxNodeData], str]
    latest_version: Callable[[ProxmoxNodeData], str]


NODE_UPDATES: tuple[ProxmoxNodeUpdateEntityDescription, ...] = (
    ProxmoxNodeUpdateEntityDescription(
        key="node_update",
        translation_key="node_update",
        entity_category=EntityCategory.CONFIG,
        # We count pending packages. When all are installed, both versions equal "0".
        installed_version=lambda _: "0",
        latest_version=lambda node_data: str(2),  # str(len(node_data.updates)),
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

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.PROGRESS
    )
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
        return self.entity_description.latest_version(
            self.coordinator.data[self.device_name]
        )

    async def async_release_notes(self) -> str | None:
        """Return the release notes for the update."""

        return f"A total of {self.latest_version} update(s) is/are pending installation. If you run the update, all pending updates will be installed. Please check the Proxmox VE node for details on the pending updates."

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Trigger apt dist-upgrade on the node."""
        self._attr_in_progress = True
        entry_data = self.coordinator.config_entry.data
        connect_kwargs: dict[str, Any] = {
            "host": entry_data["host"],
            "port": 22,
            "username": entry_data["username"],
            "known_hosts": None,
            "password": entry_data["password"],
        }
        try:
            async with asyncssh.connect(**connect_kwargs) as conn:
                result = await asyncio.wait_for(
                    conn.run(
                        "DEBIAN_FRONTEND=noninteractive "
                        "apt-get dist-upgrade -y "
                        "-o Dpkg::Options::='--force-confdef' "
                        "-o Dpkg::Options::='--force-confold'",
                        check=False,
                    ),
                    timeout=600,
                )
        except asyncssh.DisconnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_no_details",
            ) from err
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_connect_no_details",
            ) from err
        finally:
            self._attr_in_progress = False

        if result.exit_status != 0:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            )

        await self.coordinator.async_request_refresh()
