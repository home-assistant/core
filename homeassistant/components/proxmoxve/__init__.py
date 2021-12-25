"""Support for Proxmox VE."""
from __future__ import annotations

from datetime import timedelta
import logging

from proxmoxer import ProxmoxAPI
from proxmoxer.backends.https import AuthenticationError
from proxmoxer.core import ResourceException
import requests.exceptions
from requests.exceptions import ConnectTimeout, SSLError
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    COORDINATORS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PARSE_DATA,
    PROXMOX_CALCULATED_SENSOR_TYPES,
    PROXMOX_CLIENTS,
    Node_Type,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

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
                        vol.Optional(
                            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                        ): cv.positive_int,
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
        """
        Build the Proxmox client connection & coordinators.

        - store client for each host under hass.data[PROXMOX_CLIENTS][host].
        - store corrdinator for each host->vm/lxc under hass.data[DOMAIN][COORDINATORS][host][node][vm/lxc_id].
        """
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

    await hass.async_add_executor_job(build_client)

    coordinators: dict[str, dict[str, dict[int, DataUpdateCoordinator]]] = {}
    hass.data[DOMAIN][COORDINATORS] = coordinators

    # Create a coordinator for each vm/container
    for host_config in config[DOMAIN]:
        host_name = host_config[CONF_HOST]
        update_interval = host_config[CONF_SCAN_INTERVAL]
        coordinators[host_name] = {}

        proxmox_client = hass.data[PROXMOX_CLIENTS][host_name]

        # Skip invalid hosts
        if proxmox_client is None:
            continue

        proxmox = proxmox_client.get_api_client()

        for node_config in host_config[CONF_NODES]:
            node_name = node_config[CONF_NODE]
            node_coordinators = coordinators[host_name][node_name] = {}

            for vm_id in node_config[CONF_VMS]:
                coordinator = create_coordinator_container_vm(
                    hass,
                    proxmox,
                    host_name,
                    node_name,
                    vm_id,
                    Node_Type.TYPE_VM,
                    update_interval,
                )

                # Fetch initial data
                await coordinator.async_refresh()

                node_coordinators[vm_id] = coordinator

            for container_id in node_config[CONF_CONTAINERS]:
                coordinator = create_coordinator_container_vm(
                    hass,
                    proxmox,
                    host_name,
                    node_name,
                    container_id,
                    Node_Type.TYPE_CONTAINER,
                    update_interval,
                )

                # Fetch initial data
                await coordinator.async_refresh()

                node_coordinators[container_id] = coordinator

    for component in PLATFORMS:
        await hass.async_create_task(
            hass.helpers.discovery.async_load_platform(
                component, DOMAIN, {"config": config}, config
            )
        )

    return True


def create_coordinator_container_vm(
    hass, proxmox, host_name, node_name, vm_id, vm_type, update_interval
):
    """Create and return a DataUpdateCoordinator for a vm/container."""

    async def async_update_data():
        """Call the api and handle the response."""

        def poll_api():
            """Call the api."""
            vm_status = call_api_get_status(proxmox, node_name, vm_id, vm_type)
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
        update_interval=timedelta(seconds=update_interval),
    )


def parse_api_container_vm(status):
    """
    Parse api data calculate additional fields and return it formatted in a dictionary.

    It is implemented in this way to allow for more data to be added for sensors
    in the future.
    """
    data = {v: status[v] for v in PARSE_DATA}
    data_calc = {
        sensor.key: sensor.calculation(data)
        for sensor in PROXMOX_CALCULATED_SENSOR_TYPES
    }
    data.update(data_calc)

    return data


def call_api_get_status(proxmox, node_name, vm_id, vm_type):
    """Make proper api calls."""
    status = None

    try:
        if vm_type is Node_Type.TYPE_VM:
            status = proxmox.nodes(node_name).qemu(vm_id).status.current.get()
        elif vm_type is Node_Type.TYPE_CONTAINER:
            status = proxmox.nodes(node_name).lxc(vm_id).status.current.get()
    except (ResourceException, requests.exceptions.ConnectionError):
        return None

    return status


def compile_device_info(host_name, node_name, mid, name) -> DeviceInfo:
    """Return Device Info of the Server."""

    return DeviceInfo(  # TODO - add SW version and such from https://pve.proxmox.com/pve-docs/api-viewer/#/version
        entry_type=DeviceEntryType.SERVICE,
        identifiers={
            ("Domain", DOMAIN),
            ("Host", host_name),
            ("Node", node_name),
            ("ID", mid),
            ("Name", name),
        },
        name=name,
        suggested_area="Server",
        default_manufacturer="PROXMOX",
        via_device=(DOMAIN, host_name),
    )


class ProxmoxEntity(CoordinatorEntity):
    """Represents any entity created for the Proxmox VE platform."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        name: str,
        unique_id: str,
    ):
        """Initialize the Proxmox entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._available = True
        self._attr_device_info = device_info
        self._attr_name = name
        self._attr_unique_id = unique_id

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
