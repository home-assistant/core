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
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .common import sanitize_config_entry
from .const import (
    CONF_NODE,
    CONF_TOKEN,
    CONF_TOKEN_ID,
    CONF_TOKEN_SECRET,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

type ProxmoxConfigEntry = ConfigEntry[ProxmoxCoordinator]

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class ProxmoxNodeData:
    """All resources for a single Proxmox node."""

    node: dict[str, Any] = field(default_factory=dict)
    vms: dict[int, dict[str, Any]] = field(default_factory=dict)
    containers: dict[int, dict[str, Any]] = field(default_factory=dict)


class ProxmoxCoordinator(DataUpdateCoordinator[dict[str, ProxmoxNodeData]]):
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
        self.permissions: dict[str, dict[str, int]] = {}

        self.new_nodes_callbacks: list[Callable[[list[ProxmoxNodeData]], None]] = []
        self.new_vms_callbacks: list[
            Callable[[list[tuple[ProxmoxNodeData, dict[str, Any]]]], None]
        ] = []
        self.new_containers_callbacks: list[
            Callable[[list[tuple[ProxmoxNodeData, dict[str, Any]]]], None]
        ] = []

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.hass.async_add_executor_job(self._init_proxmox)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except SSLError as err:
            raise ConfigEntryError(
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
        except ProxmoxServerError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="api_error_details",
                translation_placeholders={"error": repr(err)},
            ) from err
        except ProxmoxPermissionsError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="permissions_error",
            ) from err
        except ProxmoxNodesNotFoundError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="no_nodes_found",
            ) from err
        except requests.exceptions.ConnectionError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def _async_update_data(self) -> dict[str, ProxmoxNodeData]:
        """Fetch data from Proxmox VE API."""

        try:
            nodes, vms_containers = await self.hass.async_add_executor_job(
                self._fetch_all_nodes
            )
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
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
        except ResourceException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_nodes_found",
            ) from err
        except requests.exceptions.ConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err

        data: dict[str, ProxmoxNodeData] = {}
        for node, (vms, containers) in zip(nodes, vms_containers, strict=True):
            data[node[CONF_NODE]] = ProxmoxNodeData(
                node=node,
                vms={int(vm["vmid"]): vm for vm in vms},
                containers={
                    int(container["vmid"]): container for container in containers
                },
            )

        self._async_add_remove_nodes(data)
        return data

    def _init_proxmox(self) -> None:
        """Initialize ProxmoxAPI instance."""
        data = sanitize_config_entry(self.config_entry.data)
        auth_kwargs = {
            "password": data.get(CONF_PASSWORD),
        }
        if data.get(CONF_TOKEN):
            auth_kwargs = {
                "token_name": data[CONF_TOKEN_ID],
                "token_value": data[CONF_TOKEN_SECRET],
            }
        _LOGGER.debug(
            "Connecting as %s to %s using %s",
            data[CONF_USERNAME],
            data[CONF_HOST],
            auth_kwargs.keys(),
        )
        self.proxmox = ProxmoxAPI(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            user=data[CONF_USERNAME],
            verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            **auth_kwargs,
        )

        try:
            self.permissions = self.proxmox.access.permissions.get() or {}
        except ResourceException as err:
            if 400 <= err.status_code < 500:
                raise ProxmoxPermissionsError from err
            raise ProxmoxServerError from err

        try:
            self.proxmox.nodes.get()
        except ResourceException as err:
            if 400 <= err.status_code < 500:
                raise ProxmoxNodesNotFoundError from err
            raise ProxmoxServerError from err

    def _fetch_all_nodes(
        self,
    ) -> tuple[
        list[dict[str, Any]], list[tuple[list[dict[str, Any]], list[dict[str, Any]]]]
    ]:
        """Fetch all nodes, and then proceed to the VMs and containers."""
        nodes = self.proxmox.nodes.get() or []
        vms_containers = [self._get_vms_containers(node) for node in nodes]
        return nodes, vms_containers

    def _get_vms_containers(
        self,
        node: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Get vms and containers for a node."""
        vms = self.proxmox.nodes(node[CONF_NODE]).qemu.get() or []
        containers = self.proxmox.nodes(node[CONF_NODE]).lxc.get() or []
        return vms, containers

    def _async_add_remove_nodes(self, data: dict[str, ProxmoxNodeData]) -> None:
        """Add new nodes/VMs/containers, track removals."""
        current_nodes = set(data.keys())
        self.known_nodes &= current_nodes
        new_nodes = current_nodes - self.known_nodes
        if new_nodes:
            _LOGGER.debug("New nodes found: %s", new_nodes)
            self.known_nodes.update(new_nodes)
            new_node_data = [data[node_name] for node_name in new_nodes]
            for nodes_callback in self.new_nodes_callbacks:
                nodes_callback(new_node_data)

        # And yes, track new VM's and containers as well
        current_vms = {
            (node_name, vmid)
            for node_name, node_data in data.items()
            for vmid in node_data.vms
        }
        self.known_vms &= current_vms
        new_vms = current_vms - self.known_vms
        if new_vms:
            _LOGGER.debug("New VMs found: %s", new_vms)
            self.known_vms.update(new_vms)
            new_vm_data = [
                (data[node_name], data[node_name].vms[vmid])
                for node_name, vmid in new_vms
            ]
            for vms_callback in self.new_vms_callbacks:
                vms_callback(new_vm_data)

        current_containers = {
            (node_name, vmid)
            for node_name, node_data in data.items()
            for vmid in node_data.containers
        }
        self.known_containers &= current_containers
        new_containers = current_containers - self.known_containers
        if new_containers:
            _LOGGER.debug("New containers found: %s", new_containers)
            self.known_containers.update(new_containers)
            new_container_data = [
                (data[node_name], data[node_name].containers[vmid])
                for node_name, vmid in new_containers
            ]
            for containers_callback in self.new_containers_callbacks:
                containers_callback(new_container_data)


class ProxmoxSetupError(Exception):
    """Base exception for Proxmox setup issues."""


class ProxmoxNodesNotFoundError(ProxmoxSetupError):
    """Raised when the API works but no nodes are visible."""


class ProxmoxPermissionsError(ProxmoxSetupError):
    """Raised when failing to retrieve permissions."""


class ProxmoxServerError(ProxmoxSetupError):
    """Raised when the Proxmox server returns an error."""
