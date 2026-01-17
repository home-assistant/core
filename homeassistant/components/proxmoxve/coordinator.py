"""Data Update Coordinator for Proxmox VE integration."""

from __future__ import annotations

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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_NODE, CONF_REALM, DEFAULT_VERIFY_SSL, DOMAIN

type ProxmoxConfigEntry = ConfigEntry[ProxmoxCoordinator]

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class ProxmoxNodeData:
    """All resources for a single Proxmox node."""

    vms: dict[int, dict[str, Any]] = field(default_factory=dict)
    containers: dict[int, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class ProxmoxCoordinatorData:
    """Snapshot of Proxmox state grouped by node."""

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
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except SSLError as err:
            raise ConfigEntryAuthFailed(
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
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_nodes_found",
                translation_placeholders={"error": repr(err)},
            ) from err

        data = ProxmoxCoordinatorData()
        for node, (vms, containers) in zip(nodes, vms_containers, strict=True):
            data.nodes[node[CONF_NODE]] = ProxmoxNodeData(
                vms={int(vm["vmid"]): vm for vm in vms if "vmid" in vm},
                containers={
                    int(container["vmid"]): container
                    for container in containers
                    if "vmid" in container
                },
            )
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
