"""Data Update Coordinator for Proxmox VE integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from proxmoxer import AuthenticationError, ProxmoxAPI
from proxmoxer.core import ResourceException
import requests
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_NODE, CONF_REALM, DEFAULT_VERIFY_SSL, DOMAIN

type ProxmoxConfigEntry = ConfigEntry[ProxmoxCoordinator]

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class ProxmoxNodeData:
    """All resources for a single Proxmox node."""

    node: dict[str, str] = field(default_factory=dict)
    vms: dict[int, dict[str, Any]] = field(default_factory=dict)
    containers: dict[int, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class ProxmoxCoordinatorData:
    """Proxmox state grouped by node."""

    nodes: dict[str, ProxmoxNodeData] = field(default_factory=dict)


class ProxmoxCoordinator(DataUpdateCoordinator[ProxmoxCoordinatorData]):
    """Data Update Coordinator for Proxmox VE integration."""

    config_entry: ProxmoxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ProxmoxConfigEntry,
    ) -> None:
        """Initialize the Proxmox VE coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.proxmox: ProxmoxAPI

        self.known_nodes: set[str] = set()
        self.known_vms: set[tuple[str, int]] = set()
        self.known_containers: set[tuple[str, int]] = set()

        self.new_nodes_callbacks: list[Callable[[list[ProxmoxNodeData]], None]] = []
        self.new_vms_callbacks: list[
            Callable[[list[tuple[ProxmoxNodeData, dict[str, Any]]]], None]
        ] = []
        self.new_containers_callbacks: list[
            Callable[[list[tuple[ProxmoxNodeData, dict[str, Any]]]], None]
        ] = []

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        user_id = (
            self.config_entry.data[CONF_USERNAME]
            if "@" in self.config_entry.data[CONF_USERNAME]
            else f"{self.config_entry.data[CONF_USERNAME]}@{self.config_entry.data[CONF_REALM]}"
        )
        try:
            self.proxmox = await self.hass.async_add_executor_job(
                self._create_proxmox_api,
                self.config_entry.data[CONF_HOST],
                self.config_entry.data[CONF_PORT],
                user_id,
                self.config_entry.data[CONF_PASSWORD],
                self.config_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )
            await self.hass.async_add_executor_job(self.proxmox.nodes.get)
        except AuthenticationError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except SSLError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="ssl_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except ConnectTimeout as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_nodes_found",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def _async_update_data(self) -> ProxmoxCoordinatorData:
        """Fetch data from Proxmox VE API."""
        try:
            nodes = await self.hass.async_add_executor_job(self.proxmox.nodes.get)
            vms_containers = [
                await self.hass.async_add_executor_job(self._get_vms_containers, node)
                for node in nodes
            ]
        except AuthenticationError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except SSLError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="ssl_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except ConnectTimeout as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_nodes_found",
                translation_placeholders={"error": repr(err)},
            ) from err

        data = ProxmoxCoordinatorData()
        for node, (vms, containers) in zip(nodes, vms_containers, strict=True):
            data.nodes[node[CONF_NODE]] = ProxmoxNodeData(
                node=node,
                vms={int(vm["vmid"]): vm for vm in vms},
                containers={
                    int(container["vmid"]): container for container in containers
                },
            )

        self._async_add_remove_nodes(data)
        return data

    @staticmethod
    def _create_proxmox_api(
        host: str,
        port: int,
        user_id: str,
        password: str,
        verify_ssl: bool,
    ) -> ProxmoxAPI:
        """Create a ProxmoxAPI instance - needed for the executor job."""
        return ProxmoxAPI(
            host=host,
            user=user_id,
            password=password,
            verify_ssl=verify_ssl,
            port=port,
        )

    def _get_vms_containers(
        self,
        node: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Get vms and containers for a node."""
        vms = self.proxmox.nodes(node[CONF_NODE]).qemu.get()
        containers = self.proxmox.nodes(node[CONF_NODE]).lxc.get()
        assert vms is not None and containers is not None
        return vms, containers

    def _async_add_remove_nodes(self, data: ProxmoxCoordinatorData) -> None:
        """Add new nodes/VMs/containers, track removals."""
        current_nodes = set(data.nodes.keys())
        new_nodes = current_nodes - self.known_nodes
        if new_nodes:
            _LOGGER.debug("New nodes found: %s", new_nodes)
            self.known_nodes.update(new_nodes)

        # And yes, track new VM's and containers as well
        current_vms = {
            (node_name, vmid)
            for node_name, node_data in data.nodes.items()
            for vmid in node_data.vms
        }
        new_vms = current_vms - self.known_vms
        if new_vms:
            _LOGGER.debug("New VMs found: %s", new_vms)
            self.known_vms.update(new_vms)

        current_containers = {
            (node_name, vmid)
            for node_name, node_data in data.nodes.items()
            for vmid in node_data.containers
        }
        new_containers = current_containers - self.known_containers
        if new_containers:
            _LOGGER.debug("New containers found: %s", new_containers)
            self.known_containers.update(new_containers)
