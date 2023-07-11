"""Support for Proxmox VE."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from proxmoxer import AuthenticationError, ProxmoxAPI
from proxmoxer.core import ResourceException
import requests.exceptions
from requests.exceptions import ConnectTimeout, SSLError
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    _LOGGER,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    COORDINATORS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PROXMOX_CLIENTS,
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the platform."""
    hass.data.setdefault(DOMAIN, {})

    def build_client() -> ProxmoxAPI:
        """Build the Proxmox client connection."""
        hass.data[PROXMOX_CLIENTS] = {}

        for entry in config[DOMAIN]:
            host = entry[CONF_HOST]
            port = entry[CONF_PORT]
            user = entry[CONF_USERNAME]
            realm = entry[CONF_REALM]
            password = entry[CONF_PASSWORD]
            verify_ssl = entry[CONF_VERIFY_SSL]

            hass.data[PROXMOX_CLIENTS][host] = None

            try:
                # Construct an API client with the given data for the given host
                proxmox_client = ProxmoxClient(
                    host, port, user, realm, password, verify_ssl
                )
                proxmox_client.build_client()
            except AuthenticationError:
                _LOGGER.warning(
                    "Invalid credentials for proxmox instance %s:%d", host, port
                )
                continue
            except SSLError:
                _LOGGER.error(
                    (
                        "Unable to verify proxmox server SSL. "
                        'Try using "verify_ssl: false" for proxmox instance %s:%d'
                    ),
                    host,
                    port,
                )
                continue
            except ConnectTimeout:
                _LOGGER.warning("Connection to host %s timed out during setup", host)
                continue
            except requests.exceptions.ConnectionError:
                _LOGGER.warning("Host %s is not reachable", host)
                continue

            hass.data[PROXMOX_CLIENTS][host] = proxmox_client

    await hass.async_add_executor_job(build_client)

    coordinators: dict[
        str, dict[str, dict[int, DataUpdateCoordinator[dict[str, Any] | None]]]
    ] = {}
    hass.data[DOMAIN][COORDINATORS] = coordinators

    # Create a coordinator for each vm/container
    for host_config in config[DOMAIN]:
        host_name = host_config["host"]
        coordinators[host_name] = {}

        proxmox_client = hass.data[PROXMOX_CLIENTS][host_name]

        # Skip invalid hosts
        if proxmox_client is None:
            continue

        proxmox = proxmox_client.get_api_client()

        for node_config in host_config["nodes"]:
            node_name = node_config["node"]
            node_coordinators = coordinators[host_name][node_name] = {}

            for vm_id in node_config["vms"]:
                coordinator = create_coordinator_container_vm(
                    hass, proxmox, host_name, node_name, vm_id, TYPE_VM
                )

                # Fetch initial data
                await coordinator.async_refresh()

                node_coordinators[vm_id] = coordinator

            for container_id in node_config["containers"]:
                coordinator = create_coordinator_container_vm(
                    hass, proxmox, host_name, node_name, container_id, TYPE_CONTAINER
                )

                # Fetch initial data
                await coordinator.async_refresh()

                node_coordinators[container_id] = coordinator

    for component in PLATFORMS:
        await hass.async_create_task(
            async_load_platform(hass, component, DOMAIN, {"config": config}, config)
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
            vm_status = call_api_container_vm(proxmox, node_name, vm_id, vm_type)
            return vm_status

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


def parse_api_container_vm(status: dict[str, Any]) -> dict[str, Any]:
    """Get the container or vm api data and return it formatted in a dictionary.

    It is implemented in this way to allow for more data to be added for sensors
    in the future.
    """

    return {"status": status["status"], "name": status["name"]}


def call_api_container_vm(
    proxmox: ProxmoxAPI,
    node_name: str,
    vm_id: int,
    machine_type: int,
) -> dict[str, Any] | None:
    """Make proper api calls."""
    status = None

    try:
        if machine_type == TYPE_VM:
            status = proxmox.nodes(node_name).qemu(vm_id).status.current.get()
        elif machine_type == TYPE_CONTAINER:
            status = proxmox.nodes(node_name).lxc(vm_id).status.current.get()
    except (ResourceException, requests.exceptions.ConnectionError):
        return None

    return status


class ProxmoxClient:
    """A wrapper for the proxmoxer ProxmoxAPI client."""

    _proxmox: ProxmoxAPI

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        realm: str,
        password: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize the ProxmoxClient."""

        self._host = host
        self._port = port
        self._user = user
        self._realm = realm
        self._password = password
        self._verify_ssl = verify_ssl

    def build_client(self) -> None:
        """Construct the ProxmoxAPI client.

        Allows inserting the realm within the `user` value.
        """

        if "@" in self._user:
            user_id = self._user
        else:
            user_id = f"{self._user}@{self._realm}"

        self._proxmox = ProxmoxAPI(
            self._host,
            port=self._port,
            user=user_id,
            password=self._password,
            verify_ssl=self._verify_ssl,
        )

    def get_api_client(self) -> ProxmoxAPI:
        """Return the ProxmoxAPI client."""
        return self._proxmox
