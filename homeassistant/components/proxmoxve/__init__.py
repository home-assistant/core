"""Support for Proxmox VE."""
from __future__ import annotations

from datetime import timedelta
import logging

from proxmoxer import ProxmoxAPI
from proxmoxer.backends.https import AuthenticationError
from proxmoxer.core import ResourceException
import requests.exceptions
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_REALM,
    COORDINATORS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
    PROXMOX_CLIENT,
    PROXMOX_CLIENTS,
    TYPE_CONTAINER,
    TYPE_VM,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the platform."""

    if DOMAIN not in config:
        return True

    hass.data.setdefault(DOMAIN, {})

    hass.data[PROXMOX_CLIENTS] = {}

    for entry in config[DOMAIN]:
        host = entry[CONF_HOST]
        port = entry.get(CONF_PORT, DEFAULT_PORT)
        user = entry[CONF_USERNAME]
        realm = entry.get(CONF_REALM, DEFAULT_REALM)
        password = entry[CONF_PASSWORD]
        verify_ssl = entry.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

        hass.data[PROXMOX_CLIENTS][host] = None

        try:
            # Construct an API client with the given data for the given host
            proxmox_client = ProxmoxClient(
                host, port, user, realm, password, verify_ssl
            )

            hass.async_add_executor_job(proxmox_client.build_client)
        except AuthenticationError:
            _LOGGER.warning(
                "Invalid credentials for proxmox instance %s:%d", host, port
            )
            continue
        except SSLError:
            _LOGGER.error(
                "Unable to verify proxmox server SSL. "
                'Try using "verify_ssl: false" for proxmox instance %s:%d',
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

    coordinators: dict[str, dict[str, dict[int, DataUpdateCoordinator]]] = {}
    hass.data[DOMAIN][COORDINATORS] = coordinators

    # Create a coordinator for each vm/container
    for host_config in config[DOMAIN]:
        host_name = host_config["host"]
        coordinators[host_name] = {}

    # import to config flow
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the platform."""

    entry_data = config_entry.data

    hass.data[PROXMOX_CLIENTS] = {}

    host = entry_data[CONF_HOST]
    port = entry_data[CONF_PORT]
    user = entry_data[CONF_USERNAME]
    realm = entry_data[CONF_REALM]
    password = entry_data[CONF_PASSWORD]
    verify_ssl = entry_data[CONF_VERIFY_SSL]

    try:
        # Construct an API client with the given data for the given host
        proxmox_client = ProxmoxClient(host, port, user, realm, password, verify_ssl)
        await hass.async_add_executor_job(proxmox_client.build_client)
    except AuthenticationError:
        _LOGGER.warning("Invalid credentials for proxmox instance %s:%d", host, port)
        return False
    except SSLError:
        _LOGGER.error(
            "Unable to verify proxmox server SSL. "
            'Try using "verify_ssl: false" for proxmox instance %s:%d',
            host,
            port,
        )
        return False
    except ConnectTimeout:
        _LOGGER.warning("Connection to host %s timed out during setup", host)
        return False

    coordinators: dict[str, dict[str, dict[int, DataUpdateCoordinator]]] = {}

    proxmox = await hass.async_add_executor_job(proxmox_client.get_api_client)

    for node_config in entry_data["nodes"]:
        node_name = node_config["name"]
        node_coordinators = coordinators[node_name] = {}

        for vm_id in node_config["vms"]:
            coordinator = create_coordinator_container_vm(
                hass, proxmox, entry_data["host"], node_name, vm_id, TYPE_VM
            )

            # Fetch initial data
            await coordinator.async_refresh()

            node_coordinators[vm_id] = coordinator

        for container_id in node_config["containers"]:
            coordinator = create_coordinator_container_vm(
                hass,
                proxmox,
                entry_data["host"],
                node_name,
                container_id,
                TYPE_CONTAINER,
            )

            # Fetch initial data
            await coordinator.async_refresh()

            node_coordinators[container_id] = coordinator

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        PROXMOX_CLIENT: proxmox_client,
        COORDINATORS: coordinators,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


def create_coordinator_container_vm(
    hass, proxmox, host_name, node_name, vm_id, vm_type
):
    """Create and return a DataUpdateCoordinator for a vm/container."""

    async def async_update_data():
        """Call the api and handle the response."""

        def poll_api():
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


def parse_api_container_vm(status):
    """Get the container or vm api data and return it formatted in a dictionary.

    It is implemented in this way to allow for more data to be added for sensors
    in the future.
    """

    return {"status": status["status"], "name": status["name"]}


def call_api_container_vm(proxmox, node_name, vm_id, machine_type):
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


class ProxmoxEntity(CoordinatorEntity):
    """Represents any entity created for the Proxmox VE platform."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        # host_name,
        node_name,
        vm_id=None,
    ):
        """Initialize the Proxmox entity."""
        super().__init__(coordinator)

        self.coordinator = coordinator
        self._unique_id = unique_id
        self._name = name
        # self._host_name = host_name
        self._icon = icon
        self._available = True
        self._node_name = node_name
        self._vm_id = vm_id

        self._state = None

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self._available


class ProxmoxClient:
    """A wrapper for the proxmoxer ProxmoxAPI client."""

    def __init__(self, host, port, user, realm, password, verify_ssl):
        """Initialize the ProxmoxClient."""

        self._host = host
        self._port = port
        self._user = user
        self._realm = realm
        self._password = password
        self._verify_ssl = verify_ssl

        self._proxmox = None
        self._connection_start_time = None

    def build_client(self):
        """Construct the ProxmoxAPI client. Allows inserting the realm within the `user` value."""

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

    def get_api_client(self):
        """Return the ProxmoxAPI client."""
        return self._proxmox
