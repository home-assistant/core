"""Data Update Coordinator for Proxmox VE integration."""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import timedelta
import logging
from typing import Any, override

from aioproxmox import ProxmoxVE
from aioproxmox.exceptions import (
    ProxmoxAPIError,
    ProxmoxAuthError,
    ProxmoxConnectionError,
    ProxmoxSSLError,
    ProxmoxTimeoutError,
)
from aioproxmox.model import PVEPermissions
from aioproxmox.model.pve import (
    ClusterNodeResource,
    ContainerResource,
    NodeAptUpdateProperty,
    NodeStorageResource,
    NodeTask,
    NodeVersion,
    OperationalStatus,
    QemuResource,
)
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .common import sanitize_config_entry
from .const import (
    CONF_TOKEN_ID,
    CONF_TOKEN_SECRET,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    ProxmoxPermission,
)

type ProxmoxConfigEntry = ConfigEntry[ProxmoxRuntimeData]

STATUS_UPDATE_INTERVAL = timedelta(seconds=60)
SOFTWARE_UPDATE_INTERVAL = timedelta(minutes=30)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class NodeResources:
    """Raw API resources fetched for a single Proxmox node."""

    vms: list[QemuResource]
    containers: list[ContainerResource]
    storages: list[NodeStorageResource]
    backups: list[NodeTask]


@dataclass(slots=True, kw_only=True)
class ProxmoxNodeData:
    """All resources for a single Proxmox node."""

    node: ClusterNodeResource
    vms: dict[int, QemuResource] = field(default_factory=dict)
    containers: dict[int, ContainerResource] = field(default_factory=dict)
    storages: dict[str, NodeStorageResource] = field(default_factory=dict)
    backups: list[NodeTask] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class ProxmoxNodeSoftware:
    """Version and pending updates of a single Proxmox node."""

    version: NodeVersion
    update: list[NodeAptUpdateProperty] | None


@dataclass(slots=True, kw_only=True)
class ProxmoxRuntimeData:
    """Runtime data of a Proxmox VE config entry."""

    status: ProxmoxStatusCoordinator
    software: ProxmoxSoftwareCoordinator


@contextmanager
def _translate_update_errors() -> Generator[None]:
    """Translate aioproxmox errors raised during a coordinator update."""
    try:
        yield
    except ProxmoxAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except ProxmoxSSLError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="ssl_error",
        ) from err
    except ProxmoxTimeoutError as err:
        raise UpdateFailedUnreachable(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
        ) from err
    except ProxmoxAPIError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="api_error_details",
        ) from err
    except ProxmoxConnectionError as err:
        raise UpdateFailedUnreachable(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err


class ProxmoxStatusCoordinator(DataUpdateCoordinator[dict[str, ProxmoxNodeData]]):
    """Coordinator for the status of Proxmox VE nodes, guests and storages."""

    config_entry: ProxmoxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ProxmoxConfigEntry,
    ) -> None:
        """Initialize the Proxmox VE status coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_status",
            update_interval=STATUS_UPDATE_INTERVAL,
        )
        self.proxmox: ProxmoxVE

        self.known_nodes: set[str] = set()
        self.known_vms: set[tuple[str, int]] = set()
        self.known_containers: set[tuple[str, int]] = set()
        self.known_storages: set[tuple[str, str]] = set()
        self.permissions = PVEPermissions()

        self.new_nodes_callbacks: list[Callable[[list[ProxmoxNodeData]], None]] = []
        self.new_vms_callbacks: list[
            Callable[[list[tuple[ProxmoxNodeData, QemuResource]]], None]
        ] = []
        self.new_containers_callbacks: list[
            Callable[[list[tuple[ProxmoxNodeData, ContainerResource]]], None]
        ] = []
        self.new_storages_callbacks: list[
            Callable[[list[tuple[ProxmoxNodeData, NodeStorageResource]]], None]
        ] = []

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self._init_proxmox()
        except ProxmoxAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except ProxmoxSSLError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="ssl_error",
            ) from err
        except ProxmoxTimeoutError as err:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err
        except ProxmoxAPIError as err:
            if 400 <= err.status < 500:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="permissions_error"
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error_details",
            ) from err
        except ProxmoxConnectionError as err:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    @override
    async def _async_update_data(self) -> dict[str, ProxmoxNodeData]:
        """Fetch data from Proxmox VE API."""
        with _translate_update_errors():
            node_pairs = await self._fetch_all_nodes()

        data: dict[str, ProxmoxNodeData] = {}
        for node, resources in node_pairs:
            data[node.node] = ProxmoxNodeData(
                node=node,
                vms={vm.vmid: vm for vm in resources.vms},
                containers={
                    container.vmid: container for container in resources.containers
                },
                storages={s.storage: s for s in resources.storages},
                backups=resources.backups,
            )

        self._async_add_remove_nodes(data)
        return data

    async def _init_proxmox(self) -> None:
        """Initialize ProxmoxVE instance."""
        data = sanitize_config_entry(self.config_entry.data)
        auth_kwargs: dict[str, Any] = {
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
        verify_ssl = data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        self.proxmox = ProxmoxVE(
            async_get_clientsession(self.hass, verify_ssl=verify_ssl),
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            user=data[CONF_USERNAME],
            verify_ssl=verify_ssl,
            timeout=DEFAULT_TIMEOUT,
            **auth_kwargs,
        )

        await self.proxmox.connect()
        self.permissions = await self.proxmox.access.permissions()

    async def _fetch_all_nodes(self) -> list[tuple[ClusterNodeResource, NodeResources]]:
        """Fetch all nodes with their VMs, containers, storages, etc."""
        cluster_resources = await self.proxmox.cluster.resources()
        # The node VM list reports host memory; cluster resources carry the
        # guest memory that pvestatd reads from the balloon driver.
        guest_memory = {vm.vmid: vm.mem for vm in cluster_resources.qemu}
        return [
            (node, await self._get_node_data(node, guest_memory))
            for node in cluster_resources.nodes
        ]

    async def _get_node_data(
        self,
        node: ClusterNodeResource,
        guest_memory: dict[int, int],
    ) -> NodeResources:
        """Get vms, containers, storages, etc. for a node."""
        if node.status != OperationalStatus.ONLINE:
            _LOGGER.debug(
                "Node %s is offline, skipping VM/container/storage fetch", node.node
            )
            return NodeResources(
                vms=[],
                containers=[],
                storages=[],
                backups=[],
            )

        node_endpoint = self.proxmox.nodes(node.node)
        vms = [
            replace(vm, mem=guest_memory.get(vm.vmid, vm.mem))
            for vm in await node_endpoint.qemu_all()
        ]
        containers = await node_endpoint.lxc_all()
        storage_resources = await node_endpoint.storage()
        storages = storage_resources.storages
        node_tasks = await node_endpoint.tasks(typefilter="vzdump", limit=1)
        backups = node_tasks.tasks

        return NodeResources(
            vms=vms,
            containers=containers,
            storages=storages,
            backups=backups,
        )

    def _async_add_remove_nodes(self, data: dict[str, ProxmoxNodeData]) -> None:
        """Add new nodes/VMs/containers, track removals."""
        current_nodes = set(data.keys())
        self.known_nodes &= current_nodes
        new_nodes = current_nodes - self.known_nodes
        if new_nodes:
            _LOGGER.debug("New nodes found: %s", new_nodes)
            self.known_nodes.update(new_nodes)
            new_node_data = [data[node_name] for node_name in new_nodes]
            device_registry = dr.async_get(self.hass)
            for node_data in new_node_data:
                device_registry.async_get_or_create_from_info(
                    config_entry_id=self.config_entry.entry_id,
                    device_info=node_device_info(self, node_data),
                )
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

        current_storages = {
            (node_name, storage_name)
            for node_name, node_data in data.items()
            for storage_name in node_data.storages
        }
        self.known_storages &= current_storages
        new_storages = current_storages - self.known_storages
        if new_storages:
            _LOGGER.debug("New storages found: %s", new_storages)
            self.known_storages.update(new_storages)
            new_storage_data = [
                (data[node_name], data[node_name].storages[storage_name])
                for node_name, storage_name in new_storages
            ]
            for storages_callback in self.new_storages_callbacks:
                storages_callback(new_storage_data)

        self._async_remove_stale_devices(data)

    @callback
    def _async_remove_stale_devices(self, data: dict[str, ProxmoxNodeData]) -> None:
        """Remove devices for nodes/VMs/containers/storages no longer present."""
        valid_identifiers: set[str] = set()
        for node_data in data.values():
            valid_identifiers.add(
                f"{self.config_entry.entry_id}_node_{node_data.node.id}"
            )
            valid_identifiers.update(
                f"{self.config_entry.entry_id}_vm_{vmid}" for vmid in node_data.vms
            )
            valid_identifiers.update(
                f"{self.config_entry.entry_id}_container_{vmid}"
                for vmid in node_data.containers
            )
            valid_identifiers.update(
                f"{self.config_entry.entry_id}_storage_{storage}"
                for storage in node_data.storages
            )

        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            if not any(
                identifier[0] == DOMAIN and identifier[1] in valid_identifiers
                for identifier in device.identifiers
            ):
                _LOGGER.debug("Removing stale device: %s", device.identifiers)
                registry.async_remove_device(device.id)


class ProxmoxSoftwareCoordinator(DataUpdateCoordinator[dict[str, ProxmoxNodeSoftware]]):
    """Coordinator for the version and pending updates of Proxmox VE nodes."""

    config_entry: ProxmoxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ProxmoxConfigEntry,
        status: ProxmoxStatusCoordinator,
    ) -> None:
        """Initialize the Proxmox VE software coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_software",
            update_interval=SOFTWARE_UPDATE_INTERVAL,
        )
        self.status = status
        config_entry.async_on_unload(
            status.async_add_listener(self._async_status_updated)
        )

    @override
    async def _async_update_data(self) -> dict[str, ProxmoxNodeSoftware]:
        """Fetch version and pending updates of the online nodes."""
        with _translate_update_errors():
            return {
                node: await self._get_node_software(node)
                for node in self._online_nodes()
            }

    def _online_nodes(self) -> set[str]:
        """Return the names of the online nodes."""
        return {
            node_data.node.node
            for node_data in self.status.data.values()
            if node_data.node.status == OperationalStatus.ONLINE
        }

    async def _get_node_software(self, node: str) -> ProxmoxNodeSoftware:
        """Get the version and pending updates of a node."""
        node_endpoint = self.status.proxmox.nodes(node)
        update: list[NodeAptUpdateProperty] | None = None
        if self.status.permissions.has_node_permission(node, ProxmoxPermission.SYSMOD):
            update = (await node_endpoint.apt().update()).items
        return ProxmoxNodeSoftware(version=await node_endpoint.version(), update=update)

    @callback
    def _async_status_updated(self) -> None:
        """Fetch the software of nodes that came online since the last refresh."""
        if (
            self.data is not None
            and self.last_update_success
            and self._online_nodes() - self.data.keys()
        ):
            self.config_entry.async_create_background_task(
                self.hass, self.async_request_refresh(), "proxmoxve_software"
            )


def node_device_info(
    coordinator: ProxmoxStatusCoordinator, node_data: ProxmoxNodeData
) -> dr.DeviceInfo:
    """Return the device info for a Proxmox VE node device."""
    return dr.DeviceInfo(
        identifiers={
            (DOMAIN, f"{coordinator.config_entry.entry_id}_node_{node_data.node.id}")
        },
        name=node_data.node.node,
        model="Node",
        configuration_url=proxmox_node_url(coordinator, node_data.node.node),
    )


def proxmox_base_url(coordinator: ProxmoxStatusCoordinator) -> URL:
    """Return the base URL for the Proxmox VE."""
    data = coordinator.config_entry.data
    return URL.build(
        scheme="https",
        host=data[CONF_HOST],
        port=data[CONF_PORT],
    )


def proxmox_node_url(coordinator: ProxmoxStatusCoordinator, node: str) -> URL:
    """Return the URL of a Proxmox VE node."""
    return proxmox_base_url(coordinator).with_fragment(f"v1:0:=node/{node}")
