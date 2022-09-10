"""Support for Proxmox VE."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
from typing import Any

from proxmoxer import ProxmoxAPI
from proxmoxer.backends.https import AuthenticationError
from proxmoxer.core import ResourceException
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
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
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
    ProxmoxType,
)

PLATFORMS = ["binary_sensor"]

COORDINATOR_UPDATE_INTERVAL_MAP = {
    ProxmoxType.Proxmox: timedelta(minutes=60),
    ProxmoxType.Node: timedelta(minutes=30),
    ProxmoxType.QEMU: timedelta(seconds=60),
    ProxmoxType.LXC: timedelta(seconds=60),
}

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
    if DOMAIN in config:
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
    except SSLError as error:
        raise ConfigEntryNotReady(
            f"Unable to verify proxmox server SSL. Try using 'verify_ssl: false' for proxmox instance {host}:{port}"
        ) from error
    except ConnectTimeout as error:
        raise ConfigEntryNotReady(
            f"Connection to host {host} timed out during setup"
        ) from error
    except ResourceException as error:
        raise ConfigEntryNotReady from error

    proxmox = await hass.async_add_executor_job(proxmox_client.get_api_client)

    async def async_update(
        api_category: str,
        node: str | None = None,
        vm_id: int | None = None,
    ) -> dict:
        """Update the API data."""

        def poll_api():
            """Call the api."""
            api_status = {}

            try:
                if api_category == ProxmoxType.Proxmox:
                    api_status = proxmox.version.get()
                elif api_category is ProxmoxType.Node:
                    api_status = get_data_node(proxmox, node)
                elif api_category == ProxmoxType.QEMU:
                    api_status = proxmox.nodes(node).qemu(vm_id).status.current.get()
                elif api_category == ProxmoxType.LXC:
                    api_status = proxmox.nodes(node).lxc(vm_id).status.current.get()
            except AuthenticationError as error:
                raise ConfigEntryAuthFailed from error
            except SSLError as error:
                raise UpdateFailed from error
            except ConnectTimeout as error:
                raise UpdateFailed from error
            except ResourceException as error:
                raise UpdateFailed from error

            return api_status

        try:
            status = await hass.async_add_executor_job(poll_api)
        except ResourceException as error:
            raise UpdateFailed(error) from error

        return parse_api_proxmox(status, api_category)

    async def async_init_coordinator(
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize a RainMachineDataUpdateCoordinator."""
        await coordinator.async_config_entry_first_refresh()

    controller_init_tasks = []
    coordinators = {}
    for api_category, update_interval in COORDINATOR_UPDATE_INTERVAL_MAP.items():
        if api_category in (ProxmoxType.QEMU, ProxmoxType.LXC):
            for vm_id in config_entry.data[api_category]:
                coordinator = coordinators[vm_id] = DataUpdateCoordinator(
                    hass,
                    logger=LOGGER,
                    name=f"{config_entry.data[CONF_HOST]}:{config_entry.data[CONF_PORT]} - {config_entry.data[CONF_NODE]} - {vm_id} {api_category}",
                    update_interval=update_interval,
                    update_method=partial(
                        async_update,
                        api_category,
                        config_entry.data[CONF_NODE],
                        vm_id,
                    ),
                )
                controller_init_tasks.append(async_init_coordinator(coordinator))
        else:
            coordinator = coordinators[api_category] = DataUpdateCoordinator(
                hass,
                logger=LOGGER,
                name=f"{config_entry.data[CONF_HOST]}:{config_entry.data[CONF_PORT]} - {config_entry.data[CONF_NODE]} - {api_category}",
                update_interval=update_interval,
                update_method=partial(
                    async_update,
                    api_category,
                    config_entry.data[CONF_NODE],
                ),
            )
            controller_init_tasks.append(async_init_coordinator(coordinator))

    await asyncio.gather(*controller_init_tasks)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        PROXMOX_CLIENT: proxmox_client,
        COORDINATORS: coordinators,
    }

    device_info(
        hass=hass,
        config_entry=config_entry,
        api_category=ProxmoxType.Proxmox,
        create=True,
    )

    device_info(
        hass=hass,
        config_entry=config_entry,
        api_category=ProxmoxType.Node,
        create=True,
    )

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


def get_data_node(proxmox, node):
    """Get the node data in two API endpoints."""
    api_status = proxmox.nodes(node).status.get()
    if nodes_api := proxmox.nodes.get():
        for node_api in nodes_api:
            if node_api["node"] == node:
                api_status["status"] = node_api["status"]
                api_status["cpu_node"] = node_api["cpu"]
                break
    return api_status


def parse_api_proxmox(status, api_category):
    """Get the container or vm api data and return it formatted in a dictionary.

    It is implemented in this way to allow for more data to be added for sensors
    in the future.
    """

    memory_free: float | None = None

    LOGGER.debug("Raw status %s: %s", api_category, status)

    if api_category == ProxmoxType.Proxmox:
        return {
            "version": status["version"],
        }

    if api_category is ProxmoxType.Node:
        return {
            "status": status["status"],
            "uptime": status["uptime"],
            "model": status["cpuinfo"]["model"],
            "cpu": status["cpu_node"],
            "memory_used": status["memory"]["used"],
            "memory_total": status["memory"]["total"],
            "memory_free": status["memory"]["free"],
            "swap_total": status["swap"]["total"],
            "swap_free": status["swap"]["free"],
        }

    if api_category in (ProxmoxType.QEMU, ProxmoxType.LXC):
        if status["status"] == "running":
            if api_category == ProxmoxType.QEMU:
                memory_free = status["freemem"]

        return {
            "status": status["status"],
            "uptime": status["uptime"],
            "name": status["name"],
            "cpu": status["cpu"],
            "memory_total": status["maxmem"],
            "memory_used": status["mem"],
            "memory_free": memory_free,
            "network_in": status["netin"],
            "network_out": status["netout"],
            "disk_total": status["maxdisk"],
            "disk_used": status["disk"],
        }


def device_info(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    api_category: ProxmoxType,
    vm_id: int | None = None,
    create: bool | None = False,
):
    """Return the Device Info."""

    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]

    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    node = config_entry.data[CONF_NODE]

    proxmox_version = None
    coordinator = coordinators[ProxmoxType.Proxmox]
    if not (coordinator_data := coordinator.data) is None:
        proxmox_version = f"Proxmox {coordinator_data['version']}"

    if api_category in (ProxmoxType.QEMU, ProxmoxType.LXC):
        coordinator = coordinators[vm_id]
        if not (coordinator_data := coordinator.data) is None:
            vm_name = coordinator_data["name"]

        name = f"{node} {vm_name} ({vm_id})"
        host_port_node_vm = f"{host}_{port}_{node}_{vm_id}"
        url = f"https://{host}:{port}/#v1:0:={api_category}/{vm_id}"
        via_device = f"{host}_{port}_{node}"
        default_model = api_category.upper()
    elif api_category is ProxmoxType.Node:
        coordinator = coordinators[ProxmoxType.Node]
        if not (coordinator_data := coordinator.data) is None:
            model_processor = coordinator_data["model"]

        name = f"Node {node} - {host}:{port}"
        host_port_node_vm = f"{host}_{port}_{node}"
        url = f"https://{host}:{port}/#v1:0:=node/{node}"
        via_device = f"{host}_{port}"
        default_model = model_processor
    else:
        name = f"Host {host}:{port}"
        host_port_node_vm = f"{host}_{port}"
        url = f"https://{host}:{port}/#v1:0"
        via_device = "no_device"
        default_model = "Host Proxmox"

    if create:
        device_registry = dr.async_get(hass)
        return device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            entry_type=dr.DeviceEntryType.SERVICE,
            configuration_url=url,
            identifiers={(DOMAIN, host_port_node_vm)},
            default_manufacturer=INTEGRATION_NAME,
            name=name,
            default_model=default_model,
            sw_version=proxmox_version,
            hw_version=None,
            via_device=(DOMAIN, via_device),
        )
    return DeviceInfo(
        entry_type=dr.DeviceEntryType.SERVICE,
        configuration_url=url,
        identifiers={(DOMAIN, host_port_node_vm)},
        default_manufacturer=INTEGRATION_NAME,
        name=name,
        default_model=default_model,
        sw_version=proxmox_version,
        hw_version=None,
        via_device=(DOMAIN, via_device),
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
