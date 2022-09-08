"""Support for Proxmox VE."""
from __future__ import annotations

from typing import Any

from proxmoxer import ProxmoxAPI
from proxmoxer.backends.https import AuthenticationError
from proxmoxer.core import ResourceException
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
)
from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_CONTAINERS,
    CONF_LXC,
    CONF_NODE,
    CONF_NODES,
    CONF_QEMU,
    CONF_REALM,
    CONF_VMS,
    COORDINATORS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    INTEGRATION_NAME,
    LOGGER,
    PROXMOX_CLIENT,
    UPDATE_INTERVAL,
    ProxmoxType,
)

PLATFORMS = ["binary_sensor"]

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
    # import to config flow
    LOGGER.warning(
        # Proxmox VE config flow added in 2022.10 and should be removed in 2022.12
        "Configuration of the Proxmox in YAML is deprecated and should "
        "be removed in 2022.12. Resolve the import issues and remove the "
        "YAML configuration from your configuration.yaml file",
    )
    async_create_issue(
        async_get_hass(),
        DOMAIN,
        "yaml_deprecated",
        breaks_in_ha_version="2022.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="yaml_deprecated",
        translation_placeholders={
            "integration": "Proxmox VE",
            "platform": DOMAIN,
        },
    )

    if DOMAIN in config:
        for conf in config[DOMAIN]:
            config_import: dict[str, Any] = {}
            errors = {}
            if conf.get(CONF_PORT) > 65535 or conf.get(CONF_PORT) <= 0:
                errors[CONF_PORT] = "invalid_port"
                async_create_issue(
                    async_get_hass(),
                    DOMAIN,
                    f"import_invalid_port_{DOMAIN}_{conf.get[CONF_HOST]}_{conf.get[CONF_PORT]}",
                    is_fixable=False,
                    severity=IssueSeverity.ERROR,
                    translation_key="import_invalid_port",
                    breaks_in_ha_version="2022.12.0",
                    translation_placeholders={
                        "integration": INTEGRATION_NAME,
                        "platform": DOMAIN,
                        "host": conf.get[CONF_HOST],
                        "port": conf.get[CONF_PORT],
                    },
                )
            else:

                if nodes := conf.get(CONF_NODES):
                    for node in nodes:
                        config_import = {}
                        config_import[CONF_HOST] = conf.get(CONF_HOST)
                        config_import[CONF_PORT] = conf.get(CONF_PORT, DEFAULT_PORT)
                        config_import[CONF_USERNAME] = conf.get(CONF_USERNAME)
                        config_import[CONF_PASSWORD] = conf.get(CONF_PASSWORD)
                        config_import[CONF_REALM] = conf.get(CONF_REALM, DEFAULT_REALM)
                        config_import[CONF_VERIFY_SSL] = conf.get(CONF_VERIFY_SSL)
                        config_import[CONF_NODE] = node[CONF_NODE]
                        config_import[CONF_QEMU] = node[CONF_VMS]
                        config_import[CONF_LXC] = node[CONF_CONTAINERS]

                        hass.async_create_task(
                            hass.config_entries.flow.async_init(
                                DOMAIN,
                                context={"source": SOURCE_IMPORT},
                                data=config_import,
                            )
                        )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the platform."""

    entry_data = config_entry.data

    host = entry_data[CONF_HOST]
    port = entry_data[CONF_PORT]
    user = entry_data[CONF_USERNAME]
    realm = entry_data[CONF_REALM]
    password = entry_data[CONF_PASSWORD]
    verify_ssl = entry_data[CONF_VERIFY_SSL]

    # Construct an API client with the given data for the given host
    proxmox_client = ProxmoxClient(host, port, user, realm, password, verify_ssl)
    try:
        await hass.async_add_executor_job(proxmox_client.build_client)
    except AuthenticationError as error:
        raise ConfigEntryAuthFailed from error
    except SSLError as err:
        raise ConfigEntryNotReady(
            f"Unable to verify proxmox server SSL. Try using 'verify_ssl: false' for proxmox instance {host}:{port}"
        ) from err
    except ConnectTimeout as err:
        raise ConfigEntryNotReady(
            f"Connection to host {host} timed out during setup"
        ) from err

    coordinators: dict[str, dict[str, dict[int, DataUpdateCoordinator]]] = {}

    proxmox = await hass.async_add_executor_job(proxmox_client.get_api_client)

    coordinators_nodes = coordinators[entry_data[CONF_NODE]] = {}

    # Proxmox instance info
    coordinator = create_coordinator_proxmox(
        hass, proxmox, entry_data[CONF_HOST], None, None, ProxmoxType.Proxmox
    )
    await coordinator.async_config_entry_first_refresh()
    coordinators_nodes[ProxmoxType.Proxmox] = coordinator

    # Node info
    coordinator = create_coordinator_proxmox(
        hass,
        proxmox,
        entry_data[CONF_HOST],
        entry_data[CONF_NODE],
        None,
        ProxmoxType.Node,
    )
    await coordinator.async_config_entry_first_refresh()
    coordinators_nodes[ProxmoxType.Node] = coordinator

    # QEMU info
    for vm_id in entry_data[CONF_QEMU]:
        coordinator = create_coordinator_proxmox(
            hass,
            proxmox,
            entry_data[CONF_HOST],
            entry_data[CONF_NODE],
            vm_id,
            ProxmoxType.QEMU,
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators_nodes[vm_id] = coordinator

    # LXC info
    for container_id in entry_data[CONF_LXC]:
        coordinator = create_coordinator_proxmox(
            hass,
            proxmox,
            entry_data[CONF_HOST],
            entry_data[CONF_NODE],
            container_id,
            ProxmoxType.LXC,
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators_nodes[container_id] = coordinator

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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def create_coordinator_proxmox(hass, proxmox, host, node, vm_id, info_type):
    """Create and return a DataUpdateCoordinator for a vm/container."""

    async def async_update_data():
        """Call the api and handle the response."""

        def poll_api():
            """Call the api."""
            try:
                api_status = call_api_proxmox(proxmox, node, vm_id, info_type)
            except AuthenticationError as error:
                raise ConfigEntryAuthFailed from error
            except Exception as error:
                raise ConfigEntryNotReady from error

            return api_status

        if (status := await hass.async_add_executor_job(poll_api)) is None:
            raise ConfigEntryNotReady("Error fetching data from API")

        return parse_api_proxmox(status, info_type)

    return DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"proxmox_coordinator_{host}_{node}_{vm_id}",
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )


def parse_api_proxmox(status, info_type):
    """Get the container or vm api data and return it formatted in a dictionary.

    It is implemented in this way to allow for more data to be added for sensors
    in the future.
    """
    if info_type == ProxmoxType.Proxmox:
        if (version := status["version"]) is None:
            version = None

        return {
            "version": version,
        }

    if info_type is ProxmoxType.Node:
        if (uptime := status["uptime"]) is None:
            uptime = None

        return {
            "uptime": uptime,
        }

    if info_type in (ProxmoxType.QEMU, ProxmoxType.LXC):
        if (status_vm := status["status"]) is None:
            status_vm = None
        if (name_vm := status["name"]) is None:
            name_vm = None

        return {
            "status": status_vm,
            "name": name_vm,
        }


def call_api_proxmox(proxmox, node, vm_id, info_type):
    """Make proper api calls."""
    status = None

    try:
        if info_type == ProxmoxType.Proxmox:
            status = proxmox.version.get()
        elif info_type is ProxmoxType.Node:
            status = proxmox.nodes(node).status.get()
        elif info_type == ProxmoxType.QEMU:
            status = proxmox.nodes(node).qemu(vm_id).status.current.get()
        elif info_type == ProxmoxType.LXC:
            status = proxmox.nodes(node).lxc(vm_id).status.current.get()
    except (ResourceException, requests.exceptions.ConnectionError):
        return None

    return status


def device_info(
    hass,
    config_entry,
    proxmox_type,
    vm_id,
):
    """Return the Device Info."""

    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]

    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    node = config_entry.data[CONF_NODE]

    proxmox_version = None
    coordinator = coordinators[node][ProxmoxType.Proxmox]
    if not (coordinator_data := coordinator.data) is None:
        proxmox_version = coordinator_data["version"]

    coordinator = coordinators[node][vm_id]
    if not (coordinator_data := coordinator.data) is None:
        vm_name = coordinator_data["name"]

    if proxmox_type in (ProxmoxType.QEMU, ProxmoxType.LXC):
        name = f"{node} {vm_name} ({vm_id})"
        host_port_node_vm = f"{host}_{port}_{node}_{vm_id}"
        url = f"https://{host}:{port}/#v1:0:={proxmox_type}/{vm_id}"
    elif proxmox_type is ProxmoxType.Node:
        name = node
        host_port_node_vm = f"{host}_{port}_{node}"
        url = f"https://{host}:{port}/#v1:0:=node/{node}"
    else:
        name = f"{host}"
        host_port_node_vm = f"{host}_{port}"
        url = f"https://{host}:{port}/#v1:0"

    return DeviceInfo(
        entry_type=device_registry.DeviceEntryType.SERVICE,
        configuration_url=url,
        identifiers={(DOMAIN, host_port_node_vm)},
        default_manufacturer=INTEGRATION_NAME,
        name=name,
        default_model=proxmox_type.upper(),
        sw_version=proxmox_version,
        hw_version=None,
    )


class ProxmoxEntity(CoordinatorEntity):
    """Represents any entity created for the Proxmox VE platform."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        node_name,
        vm_id=None,
    ):
        """Initialize the Proxmox entity."""
        super().__init__(coordinator)

        self.coordinator = coordinator
        self._unique_id = unique_id
        self._name = name
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
