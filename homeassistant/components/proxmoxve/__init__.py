"""Support for Proxmox VE."""

from __future__ import annotations

from datetime import timedelta
import logging
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
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import (
    ProxmoxClient,
    ResourceException,
    call_api_container_vm,
    parse_api_container_vm,
)
from .const import (
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

type ProxmoxConfigEntry = ConfigEntry[
    dict[str, dict[str, dict[int, DataUpdateCoordinator[dict[str, Any] | None]]]]
]

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

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the Proxmox configuration from YAML."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_setup(hass, config))

    return True


async def _async_setup(hass: HomeAssistant, config: ConfigType) -> None:
    for entry_config in config[DOMAIN]:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=entry_config,
        )
        if (
            result.get("type") is FlowResultType.ABORT
            and result.get("reason") != "already_configured"
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result.get('reason')}",
                breaks_in_ha_version="2026.8.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Proxmox VE",
                },
            )
            return

        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2026.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Proxmox VE",
            },
        )


async def async_setup_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Set up a ProxmoxVE instance from a config entry."""

    def build_client() -> ProxmoxClient:
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
        except SSLError as ex:
            raise ConfigEntryAuthFailed(
                f"Unable to verify proxmox server SSL. Try using 'verify_ssl: false' for proxmox instance {host}:{port}"
            ) from ex
        except ConnectTimeout as ex:
            raise ConfigEntryNotReady("Connection timed out") from ex
        except requests.exceptions.ConnectionError as ex:
            raise ConfigEntryNotReady(f"Host {host} is not reachable: {ex}") from ex
        else:
            return client

    proxmox_client = await hass.async_add_executor_job(build_client)

    coordinators: dict[
        str, dict[str, dict[int, DataUpdateCoordinator[dict[str, Any] | None]]]
    ] = {}
    entry.runtime_data = coordinators

    host_name = entry.data[CONF_HOST]
    coordinators[host_name] = {}

    proxmox: ProxmoxAPI = proxmox_client.get_api_client()

    for node_config in entry.data[CONF_NODES]:
        node_name = node_config[CONF_NODE]
        node_coordinators = coordinators[host_name][node_name] = {}

        try:
            vms, containers = await hass.async_add_executor_job(
                _get_vms_containers, proxmox, node_config
            )
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            LOGGER.error("Unable to get vms/containers for node %s: %s", node_name, err)
            continue

        for vm in vms:
            coordinator = _create_coordinator_container_vm(
                hass, entry, proxmox, host_name, node_name, vm["vmid"], TYPE_VM
            )
            await coordinator.async_config_entry_first_refresh()

            node_coordinators[vm["vmid"]] = coordinator

        for container in containers:
            coordinator = _create_coordinator_container_vm(
                hass,
                entry,
                proxmox,
                host_name,
                node_name,
                container["vmid"],
                TYPE_CONTAINER,
            )
            await coordinator.async_config_entry_first_refresh()

            node_coordinators[container["vmid"]] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _get_vms_containers(
    proxmox: ProxmoxAPI,
    node_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Get vms and containers for a node."""
    vms = proxmox.nodes(node_config[CONF_NODE]).qemu.get()
    containers = proxmox.nodes(node_config[CONF_NODE]).lxc.get()
    assert vms is not None and containers is not None
    return vms, containers


def _create_coordinator_container_vm(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
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
            LOGGER.warning(
                "Vm/Container %s unable to be found in node %s", vm_id, node_name
            )
            return None

        return parse_api_container_vm(vm_status)

    return DataUpdateCoordinator(
        hass,
        LOGGER,
        config_entry=entry,
        name=f"proxmox_coordinator_{host_name}_{node_name}_{vm_id}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )


async def async_unload_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
