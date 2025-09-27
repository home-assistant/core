"""Support for Proxmox VE."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from proxmoxer import AuthenticationError, ProxmoxAPI
import requests.exceptions
from requests.exceptions import ConnectTimeout, SSLError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import (
    ProxmoxClient,
    ResourceException,
    call_api_container_vm,
    parse_api_container_vm,
)
from .const import (
    _LOGGER,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    TYPE_CONTAINER,
    TYPE_VM,
    UPDATE_INTERVAL,
)

PLATFORMS = [Platform.BINARY_SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
                        vol.Optional(
                            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                        ): cv.boolean,
                        vol.Required(CONF_NODES): vol.All(
                            cv.ensure_list,
                            [
                                vol.Schema(
                                    {
                                        vol.Required(CONF_NODE): cv.string,
                                        vol.Optional(CONF_VMS, default=[]): [
                                            cv.positive_int
                                        ],
                                        vol.Optional(CONF_CONTAINERS, default=[]): [
                                            cv.positive_int
                                        ],
                                    }
                                )
                            ],
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a ProxmoxVE instance from a config entry."""

    def build_client() -> ProxmoxClient | None:
        """Build and return the Proxmox client connection."""
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        user = entry.data[CONF_USERNAME]
        realm = entry.data[CONF_REALM]
        password = entry.data[CONF_PASSWORD]
        verify_ssl = entry.data[CONF_VERIFY_SSL]
        try:
            client = ProxmoxClient(host, port, user, realm, password, verify_ssl)
            client.build_client()
        except AuthenticationError as ex:
            raise ConfigEntryAuthFailed("Invalid credentials") from ex
        except SSLError:
            _LOGGER.error(
                "Unable to verify proxmox server SSL. Try using 'verify_ssl: false' for proxmox instance %s:%d",
                host,
                port,
            )
        except ConnectTimeout as ex:
            raise ConfigEntryNotReady("Connection timed out") from ex
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.warning("Host %s is not reachable: %s", host, ex)
        else:
            return client
        return None

    proxmox_client = await hass.async_add_executor_job(build_client)
    if proxmox_client is None:
        return False

    coordinators: dict[
        str, dict[str, dict[int, DataUpdateCoordinator[dict[str, Any] | None]]]
    ] = {}
    entry.runtime_data = coordinators

    host_name = entry.data[CONF_HOST]
    coordinators[host_name] = {}

    proxmox: ProxmoxAPI = proxmox_client.get_api_client()

    updated_nodes: list[dict[str, Any]] = []
    for node_config in entry.data[CONF_NODES]:
        node_name = node_config[CONF_NODE]
        node_coordinators = coordinators[host_name][node_name] = {}

        try:
            vms = await hass.async_add_executor_job(
                proxmox.nodes(node_config[CONF_NODE]).qemu.get
            )
            containers = await hass.async_add_executor_job(
                proxmox.nodes(node_config[CONF_NODE]).lxc.get
            )
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            _LOGGER.error(
                "Unable to get vms/containers for node %s: %s", node_name, err
            )
            continue

        updated_node = {
            CONF_NODE: node_name,
            CONF_VMS: [vm["vmid"] for vm in vms],
            CONF_CONTAINERS: [container["vmid"] for container in containers],
        }
        updated_nodes.append(updated_node)

        for vm in vms:
            coordinator = create_coordinator_container_vm(
                hass, proxmox, host_name, node_name, vm["vmid"], TYPE_VM
            )
            await coordinator.async_refresh()

            node_coordinators[vm["vmid"]] = coordinator

        for container in containers:
            coordinator = create_coordinator_container_vm(
                hass,
                proxmox,
                host_name,
                node_name,
                container["vmid"],
                TYPE_CONTAINER,
            )
            await coordinator.async_refresh()

            node_coordinators[container["vmid"]] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Proxmox component. (deprecated)."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )
    return True


def create_coordinator_container_vm(
    hass: HomeAssistant,
    proxmox: ProxmoxAPI,
    host_name: str,
    node_name: str,
    vm_id: int,
    vm_type: int,
) -> DataUpdateCoordinator[dict[str, Any] | None]:
    """Create and return a DataUpdateCoordinator for a vm/container."""

    async def async_update_data() -> dict[str, Any] | None:
        """Call the api and handle the response."""

        def poll_api() -> dict[str, Any] | None:
            """Call the api."""
            return call_api_container_vm(proxmox, node_name, vm_id, vm_type)

        vm_status = await hass.async_add_executor_job(poll_api)

        if vm_status is None:
            _LOGGER.warning(
                "Vm/Container %s unable to be found in node %s", vm_id, node_name
            )
            return None

        return parse_api_container_vm(vm_status)

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"proxmox_coordinator_{host_name}_{node_name}_{vm_id}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )
