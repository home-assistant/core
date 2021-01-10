"""Support for Proxmox VE."""
from datetime import timedelta
import logging

from proxmoxer import ProxmoxAPI
from proxmoxer.backends.https import AuthenticationError
from proxmoxer.core import ResourceException
from requests.exceptions import SSLError
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

PLATFORMS = ["sensor", "binary_sensor"]
DOMAIN = "proxmox_custom"
PROXMOX_CLIENTS = "proxmox_clients"
CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"
IGNORED = "ignored"

COORDINATOR = "coordinator"
API_DATA = "api_data"

DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True
TYPE_VM = 0
TYPE_CONTAINER = 1
UPDATE_INTERVAL = 60  # Anything lower then 60 could result in errors with the API

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


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the platform."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][IGNORED] = []

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
                    'Unable to verify proxmox server SSL. Try using "verify_ssl: false"'
                )
                continue

            return proxmox_client

    proxmox_client = await hass.async_add_executor_job(build_client)

    async def async_update_data() -> dict:
        """Fetch data from API endpoint.

        Multiple API calls are made here because the proxmox
        API only allows for data to be polled per VM/container/node.
        """

        proxmox = proxmox_client.get_api_client()

        def poll_api() -> dict:
            data = {}

            for host_config in config[DOMAIN]:
                host_name = host_config["host"]

                data[host_name] = {}

                for node_config in host_config["nodes"]:
                    node_name = node_config["node"]
                    data[host_name][node_name] = {}

                    node_status = call_api_node(proxmox, node_name)

                    if node_status is None:
                        _LOGGER.error(f"Node {node_name} unable to be found")
                        hass.data[DOMAIN][IGNORED].append(node_name)
                        continue

                    data[host_name][node_name] = parse_api_node(node_status)

                    for vm_id in node_config["vms"]:
                        data[host_name][node_name][vm_id] = {}

                        call = call_api_container_vm(proxmox, node_name, vm_id, TYPE_VM)

                        if call is None:
                            _LOGGER.error(f"Vm/Container {vm_id} unable to be found")
                            hass.data[DOMAIN][IGNORED].append(vm_id)
                            continue

                        vm_status = call[0]
                        vm_rrd = call[1]

                        data[host_name][node_name][vm_id] = parse_api_container_vm(
                            vm_status, vm_rrd
                        )

                    for container_id in node_config["containers"]:
                        data[host_name][node_name][container_id] = {}

                        call = call_api_container_vm(
                            proxmox, node_name, container_id, TYPE_CONTAINER
                        )

                        if call is None:
                            _LOGGER.error(
                                f"Vm/Container {container_id} unable to be found"
                            )
                            hass.data[DOMAIN][IGNORED].append(container_id)
                            continue

                        container_status = call[0]
                        container_rrd = call[1]

                        data[host_name][node_name][
                            container_id
                        ] = parse_api_container_vm(container_status, container_rrd)

            return data

        return await hass.async_add_executor_job(poll_api)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="proxmox_coordinator",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    hass.data[DOMAIN][COORDINATOR] = coordinator

    # Fetch initial data
    await coordinator.async_refresh()

    hass.loop.create_task(coordinator.async_refresh())

    for component in PLATFORMS:
        await hass.async_create_task(
            hass.helpers.discovery.async_load_platform(
                component, DOMAIN, {"config": config}, config
            )
        )

    return True


def parse_api_container_vm(status, rrd):
    """Get the container or vm api data and return it formatted in a dictionary."""
    return {
        "status": status["status"],
        "uptime": status["uptime"],
        "name": status["name"],
        "memory_used": rrd["mem"],
        "memory_total": rrd["maxmem"],
        "net_out": rrd["netout"],
        "net_in": rrd["netin"],
        "cpu_use": rrd["cpu"],
        "num_cpu": rrd["maxcpu"],
    }


def parse_api_node(node_status):
    """Get the node api data and return it formatted in a dictionary."""
    return {
        "memory_used": node_status["memory"]["used"],
        "memory_total": node_status["memory"]["total"],
        "rootfs_used": node_status["rootfs"]["used"],
        "rootfs_total": node_status["rootfs"]["total"],
    }


def call_api_node(proxmox, node_name):
    """Make proper API calls and return the output."""
    try:
        node_status = proxmox.nodes(node_name).status.get()
    except ResourceException:
        return None
    return node_status


def call_api_container_vm(proxmox, node_name, vm_id, type):
    """Make proper api calls and return the output ordered into a list."""
    status = None

    try:
        if type == TYPE_VM:
            status = proxmox.nodes(node_name).qemu(vm_id).status.current.get()
        elif type == TYPE_CONTAINER:
            status = proxmox.nodes(node_name).lxc(vm_id).status.current.get()
        rrd = proxmox.nodes(node_name).qemu(vm_id).rrddata.get(timeframe="hour")
    except ResourceException:
        return None

    # This is needed because sometimes the rrd API request returns
    # data where the last datapoint isn't populated at all.
    try:
        rrd = rrd[-1]
        # try to access something that might not be there
        rrd["cpu"]
    except KeyError:
        _LOGGER.warning("rrd api returned bad info")
        rrd = rrd[-2]
        _LOGGER.warning(f"vm_rrd is now {rrd}")

    return [status, rrd]


class ProxmoxEntity(CoordinatorEntity):
    """Represents any entity created for the Proxmox VE platform."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        host_name,
        node_name,
        vm_id=None,
    ):
        """Initialize the Proxmox entity."""
        super().__init__(coordinator)

        self.coordinator = coordinator
        self._unique_id = unique_id
        self._name = name
        self._host_name = host_name
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
