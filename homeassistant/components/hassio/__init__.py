"""Support for Hass.io."""
from __future__ import annotations

from datetime import timedelta
import logging
import os
from typing import Any, NamedTuple

import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.homeassistant import (
    SERVICE_CHECK_CONFIG,
    SHUTDOWN_SERVICES,
)
import homeassistant.config as conf_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    ATTR_SERVICE,
    EVENT_CORE_CONFIG_UPDATE,
    SERVICE_HOMEASSISTANT_RESTART,
    SERVICE_HOMEASSISTANT_STOP,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, recorder
from homeassistant.helpers.device_registry import DeviceRegistry, async_get_registry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.loader import bind_hass
from homeassistant.util.dt import utcnow

from .addon_panel import async_setup_addon_panel
from .auth import async_setup_auth_view
from .const import (
    ATTR_ADDON,
    ATTR_ADDONS,
    ATTR_DISCOVERY,
    ATTR_FOLDERS,
    ATTR_HOMEASSISTANT,
    ATTR_INPUT,
    ATTR_PASSWORD,
    ATTR_REPOSITORY,
    ATTR_SLUG,
    ATTR_SNAPSHOT,
    ATTR_URL,
    ATTR_VERSION,
    DOMAIN,
    SupervisorEntityModel,
)
from .discovery import async_setup_discovery_view
from .handler import HassIO, HassioAPIError, api_data
from .http import HassIOView
from .ingress import async_setup_ingress_view
from .websocket_api import async_load_websocket_api

_LOGGER = logging.getLogger(__name__)


STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
PLATFORMS = ["binary_sensor", "sensor"]

CONF_FRONTEND_REPO = "development_repo"

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.Schema({vol.Optional(CONF_FRONTEND_REPO): cv.isdir})},
    extra=vol.ALLOW_EXTRA,
)


DATA_CORE_INFO = "hassio_core_info"
DATA_HOST_INFO = "hassio_host_info"
DATA_STORE = "hassio_store"
DATA_INFO = "hassio_info"
DATA_OS_INFO = "hassio_os_info"
DATA_SUPERVISOR_INFO = "hassio_supervisor_info"
HASSIO_UPDATE_INTERVAL = timedelta(minutes=55)

ADDONS_COORDINATOR = "hassio_addons_coordinator"

SERVICE_ADDON_START = "addon_start"
SERVICE_ADDON_STOP = "addon_stop"
SERVICE_ADDON_RESTART = "addon_restart"
SERVICE_ADDON_UPDATE = "addon_update"
SERVICE_ADDON_STDIN = "addon_stdin"
SERVICE_HOST_SHUTDOWN = "host_shutdown"
SERVICE_HOST_REBOOT = "host_reboot"
SERVICE_SNAPSHOT_FULL = "snapshot_full"
SERVICE_SNAPSHOT_PARTIAL = "snapshot_partial"
SERVICE_BACKUP_FULL = "backup_full"
SERVICE_BACKUP_PARTIAL = "backup_partial"
SERVICE_RESTORE_FULL = "restore_full"
SERVICE_RESTORE_PARTIAL = "restore_partial"


SCHEMA_NO_DATA = vol.Schema({})

SCHEMA_ADDON = vol.Schema({vol.Required(ATTR_ADDON): cv.string})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend(
    {vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)}
)

SCHEMA_BACKUP_FULL = vol.Schema(
    {vol.Optional(ATTR_NAME): cv.string, vol.Optional(ATTR_PASSWORD): cv.string}
)

SCHEMA_BACKUP_PARTIAL = SCHEMA_BACKUP_FULL.extend(
    {
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
    }
)

SCHEMA_RESTORE_FULL = vol.Schema(
    {
        vol.Exclusive(ATTR_SLUG, ATTR_SLUG): cv.slug,
        vol.Exclusive(ATTR_SNAPSHOT, ATTR_SLUG): cv.slug,
        vol.Optional(ATTR_PASSWORD): cv.string,
    },
    cv.has_at_least_one_key(ATTR_SLUG, ATTR_SNAPSHOT),
)

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend(
    {
        vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
    }
)


class APIEndpointSettings(NamedTuple):
    """Settings for API endpoint."""

    command: str
    schema: vol.Schema
    timeout: int | None = 60
    pass_data: bool = False


MAP_SERVICE_API = {
    SERVICE_ADDON_START: APIEndpointSettings("/addons/{addon}/start", SCHEMA_ADDON),
    SERVICE_ADDON_STOP: APIEndpointSettings("/addons/{addon}/stop", SCHEMA_ADDON),
    SERVICE_ADDON_RESTART: APIEndpointSettings("/addons/{addon}/restart", SCHEMA_ADDON),
    SERVICE_ADDON_UPDATE: APIEndpointSettings("/addons/{addon}/update", SCHEMA_ADDON),
    SERVICE_ADDON_STDIN: APIEndpointSettings(
        "/addons/{addon}/stdin", SCHEMA_ADDON_STDIN
    ),
    SERVICE_HOST_SHUTDOWN: APIEndpointSettings("/host/shutdown", SCHEMA_NO_DATA),
    SERVICE_HOST_REBOOT: APIEndpointSettings("/host/reboot", SCHEMA_NO_DATA),
    SERVICE_BACKUP_FULL: APIEndpointSettings(
        "/backups/new/full",
        SCHEMA_BACKUP_FULL,
        None,
        True,
    ),
    SERVICE_BACKUP_PARTIAL: APIEndpointSettings(
        "/backups/new/partial",
        SCHEMA_BACKUP_PARTIAL,
        None,
        True,
    ),
    SERVICE_RESTORE_FULL: APIEndpointSettings(
        "/backups/{slug}/restore/full",
        SCHEMA_RESTORE_FULL,
        None,
        True,
    ),
    SERVICE_RESTORE_PARTIAL: APIEndpointSettings(
        "/backups/{slug}/restore/partial",
        SCHEMA_RESTORE_PARTIAL,
        None,
        True,
    ),
    SERVICE_SNAPSHOT_FULL: APIEndpointSettings(
        "/backups/new/full",
        SCHEMA_BACKUP_FULL,
        None,
        True,
    ),
    SERVICE_SNAPSHOT_PARTIAL: APIEndpointSettings(
        "/backups/new/partial",
        SCHEMA_BACKUP_PARTIAL,
        None,
        True,
    ),
}


@bind_hass
async def async_get_addon_info(hass: HomeAssistant, slug: str) -> dict:
    """Return add-on info.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    return await hassio.get_addon_info(slug)


@bind_hass
async def async_update_diagnostics(hass: HomeAssistant, diagnostics: bool) -> dict:
    """Update Supervisor diagnostics toggle.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    return await hassio.update_diagnostics(diagnostics)


@bind_hass
@api_data
async def async_install_addon(hass: HomeAssistant, slug: str) -> dict:
    """Install add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    command = f"/addons/{slug}/install"
    return await hassio.send_command(command, timeout=None)


@bind_hass
@api_data
async def async_uninstall_addon(hass: HomeAssistant, slug: str) -> dict:
    """Uninstall add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    command = f"/addons/{slug}/uninstall"
    return await hassio.send_command(command, timeout=60)


@bind_hass
@api_data
async def async_update_addon(hass: HomeAssistant, slug: str) -> dict:
    """Update add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    command = f"/addons/{slug}/update"
    return await hassio.send_command(command, timeout=None)


@bind_hass
@api_data
async def async_start_addon(hass: HomeAssistant, slug: str) -> dict:
    """Start add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    command = f"/addons/{slug}/start"
    return await hassio.send_command(command, timeout=60)


@bind_hass
@api_data
async def async_restart_addon(hass: HomeAssistant, slug: str) -> dict:
    """Restart add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    command = f"/addons/{slug}/restart"
    return await hassio.send_command(command, timeout=None)


@bind_hass
@api_data
async def async_stop_addon(hass: HomeAssistant, slug: str) -> dict:
    """Stop add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    command = f"/addons/{slug}/stop"
    return await hassio.send_command(command, timeout=60)


@bind_hass
@api_data
async def async_set_addon_options(
    hass: HomeAssistant, slug: str, options: dict
) -> dict:
    """Set add-on options.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    command = f"/addons/{slug}/options"
    return await hassio.send_command(command, payload=options)


@bind_hass
async def async_get_addon_discovery_info(hass: HomeAssistant, slug: str) -> dict | None:
    """Return discovery data for an add-on."""
    hassio = hass.data[DOMAIN]
    data = await hassio.retrieve_discovery_messages()
    discovered_addons = data[ATTR_DISCOVERY]
    return next((addon for addon in discovered_addons if addon["addon"] == slug), None)


@bind_hass
@api_data
async def async_create_backup(
    hass: HomeAssistant, payload: dict, partial: bool = False
) -> dict:
    """Create a full or partial backup.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    backup_type = "partial" if partial else "full"
    command = f"/backups/new/{backup_type}"
    return await hassio.send_command(command, payload=payload, timeout=None)


@callback
@bind_hass
def get_info(hass):
    """Return generic information from Supervisor.

    Async friendly.
    """
    return hass.data.get(DATA_INFO)


@callback
@bind_hass
def get_host_info(hass):
    """Return generic host information.

    Async friendly.
    """
    return hass.data.get(DATA_HOST_INFO)


@callback
@bind_hass
def get_store(hass):
    """Return store information.

    Async friendly.
    """
    return hass.data.get(DATA_STORE)


@callback
@bind_hass
def get_supervisor_info(hass):
    """Return Supervisor information.

    Async friendly.
    """
    return hass.data.get(DATA_SUPERVISOR_INFO)


@callback
@bind_hass
def get_os_info(hass):
    """Return OS information.

    Async friendly.
    """
    return hass.data.get(DATA_OS_INFO)


@callback
@bind_hass
def get_core_info(hass):
    """Return Home Assistant Core information from Supervisor.

    Async friendly.
    """
    return hass.data.get(DATA_CORE_INFO)


@callback
@bind_hass
def is_hassio(hass: HomeAssistant) -> bool:
    """Return true if Hass.io is loaded.

    Async friendly.
    """
    return DOMAIN in hass.config.components


@callback
def get_supervisor_ip():
    """Return the supervisor ip address."""
    if "SUPERVISOR" not in os.environ:
        return None
    return os.environ["SUPERVISOR"].partition(":")[0]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: C901
    """Set up the Hass.io component."""
    # Check local setup
    for env in ("HASSIO", "HASSIO_TOKEN"):
        if os.environ.get(env):
            continue
        _LOGGER.error("Missing %s environment variable", env)
        if config_entries := hass.config_entries.async_entries(DOMAIN):
            hass.async_create_task(
                hass.config_entries.async_remove(config_entries[0].entry_id)
            )
        return False

    async_load_websocket_api(hass)

    host = os.environ["HASSIO"]
    websession = hass.helpers.aiohttp_client.async_get_clientsession()
    hass.data[DOMAIN] = hassio = HassIO(hass.loop, websession, host)

    if not await hassio.is_connected():
        _LOGGER.warning("Not connected with the supervisor / system too busy!")

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None:
        data = {}

    refresh_token = None
    if "hassio_user" in data:
        user = await hass.auth.async_get_user(data["hassio_user"])
        if user and user.refresh_tokens:
            refresh_token = list(user.refresh_tokens.values())[0]

            # Migrate old Hass.io users to be admin.
            if not user.is_admin:
                await hass.auth.async_update_user(user, group_ids=[GROUP_ID_ADMIN])

            # Migrate old name
            if user.name == "Hass.io":
                await hass.auth.async_update_user(user, name="Supervisor")

    if refresh_token is None:
        user = await hass.auth.async_create_system_user("Supervisor", [GROUP_ID_ADMIN])
        refresh_token = await hass.auth.async_create_refresh_token(user)
        data["hassio_user"] = user.id
        await store.async_save(data)

    # This overrides the normal API call that would be forwarded
    development_repo = config.get(DOMAIN, {}).get(CONF_FRONTEND_REPO)
    if development_repo is not None:
        hass.http.register_static_path(
            "/api/hassio/app", os.path.join(development_repo, "hassio/build"), False
        )

    hass.http.register_view(HassIOView(host, websession))

    await hass.components.panel_custom.async_register_panel(
        frontend_url_path="hassio",
        webcomponent_name="hassio-main",
        sidebar_title="Supervisor",
        sidebar_icon="hass:home-assistant",
        js_url="/api/hassio/app/entrypoint.js",
        embed_iframe=True,
        require_admin=True,
    )

    await hassio.update_hass_api(config.get("http", {}), refresh_token)

    last_timezone = None

    async def push_config(_):
        """Push core config to Hass.io."""
        nonlocal last_timezone

        new_timezone = str(hass.config.time_zone)

        if new_timezone == last_timezone:
            return

        last_timezone = new_timezone
        await hassio.update_hass_timezone(new_timezone)

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, push_config)

    await push_config(None)

    async def async_service_handler(service):
        """Handle service calls for Hass.io."""
        api_endpoint = MAP_SERVICE_API[service.service]

        if "snapshot" in service.service:
            _LOGGER.warning(
                "The service '%s' is deprecated and will be removed in Home Assistant 2021.11, use '%s' instead",
                service.service,
                service.service.replace("snapshot", "backup"),
            )
        data = service.data.copy()
        addon = data.pop(ATTR_ADDON, None)
        slug = data.pop(ATTR_SLUG, None)
        snapshot = data.pop(ATTR_SNAPSHOT, None)
        if snapshot is not None:
            _LOGGER.warning(
                "Using 'snapshot' is deprecated and will be removed in Home Assistant 2021.11, use 'slug' instead"
            )
            slug = snapshot

        payload = None

        # Pass data to Hass.io API
        if service.service == SERVICE_ADDON_STDIN:
            payload = data[ATTR_INPUT]
        elif api_endpoint.pass_data:
            payload = data

        # Call API
        try:
            await hassio.send_command(
                api_endpoint.command.format(addon=addon, slug=slug),
                payload=payload,
                timeout=api_endpoint.timeout,
            )
        except HassioAPIError:
            # The exceptions are logged properly in hassio.send_command
            pass

    for service, settings in MAP_SERVICE_API.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=settings.schema
        )

    async def update_info_data(now):
        """Update last available supervisor information."""
        try:
            hass.data[DATA_INFO] = await hassio.get_info()
            hass.data[DATA_HOST_INFO] = await hassio.get_host_info()
            hass.data[DATA_STORE] = await hassio.get_store()
            hass.data[DATA_CORE_INFO] = await hassio.get_core_info()
            hass.data[DATA_SUPERVISOR_INFO] = await hassio.get_supervisor_info()
            hass.data[DATA_OS_INFO] = await hassio.get_os_info()
            if ADDONS_COORDINATOR in hass.data:
                await hass.data[ADDONS_COORDINATOR].async_refresh()
        except HassioAPIError as err:
            _LOGGER.warning("Can't read last version: %s", err)

        hass.helpers.event.async_track_point_in_utc_time(
            update_info_data, utcnow() + HASSIO_UPDATE_INTERVAL
        )

    # Fetch last version
    await update_info_data(None)

    async def async_handle_core_service(call):
        """Service handler for handling core services."""
        if (
            call.service in SHUTDOWN_SERVICES
            and await recorder.async_migration_in_progress(hass)
        ):
            _LOGGER.error(
                "The system cannot %s while a database upgrade is in progress",
                call.service,
            )
            raise HomeAssistantError(
                f"The system cannot {call.service} "
                "while a database upgrade is in progress."
            )

        if call.service == SERVICE_HOMEASSISTANT_STOP:
            await hassio.stop_homeassistant()
            return

        errors = await conf_util.async_check_ha_config_file(hass)

        if errors:
            _LOGGER.error(
                "The system cannot %s because the configuration is not valid: %s",
                call.service,
                errors,
            )
            hass.components.persistent_notification.async_create(
                "Config error. See [the logs](/config/logs) for details.",
                "Config validating",
                f"{HASS_DOMAIN}.check_config",
            )
            raise HomeAssistantError(
                f"The system cannot {call.service} "
                f"because the configuration is not valid: {errors}"
            )

        if call.service == SERVICE_HOMEASSISTANT_RESTART:
            await hassio.restart_homeassistant()

    # Mock core services
    for service in (
        SERVICE_HOMEASSISTANT_STOP,
        SERVICE_HOMEASSISTANT_RESTART,
        SERVICE_CHECK_CONFIG,
    ):
        hass.services.async_register(HASS_DOMAIN, service, async_handle_core_service)

    # Init discovery Hass.io feature
    async_setup_discovery_view(hass, hassio)

    # Init auth Hass.io feature
    async_setup_auth_view(hass, user)

    # Init ingress Hass.io feature
    async_setup_ingress_view(hass, host)

    # Init add-on ingress panels
    await async_setup_addon_panel(hass, hassio)

    hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": "system"})
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    dev_reg = await async_get_registry(hass)
    coordinator = HassioDataUpdateCoordinator(hass, entry, dev_reg)
    hass.data[ADDONS_COORDINATOR] = coordinator
    await coordinator.async_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Pop add-on data
    hass.data.pop(ADDONS_COORDINATOR, None)

    return unload_ok


@callback
def async_register_addons_in_dev_reg(
    entry_id: str, dev_reg: DeviceRegistry, addons: list[dict[str, Any]]
) -> None:
    """Register addons in the device registry."""
    for addon in addons:
        params = {
            "config_entry_id": entry_id,
            "identifiers": {(DOMAIN, addon[ATTR_SLUG])},
            "model": SupervisorEntityModel.ADDON,
            "sw_version": addon[ATTR_VERSION],
            "name": addon[ATTR_NAME],
            "entry_type": ATTR_SERVICE,
        }
        if manufacturer := addon.get(ATTR_REPOSITORY) or addon.get(ATTR_URL):
            params["manufacturer"] = manufacturer
        dev_reg.async_get_or_create(**params)


@callback
def async_register_os_in_dev_reg(
    entry_id: str, dev_reg: DeviceRegistry, os_dict: dict[str, Any]
) -> None:
    """Register OS in the device registry."""
    params = {
        "config_entry_id": entry_id,
        "identifiers": {(DOMAIN, "OS")},
        "manufacturer": "Home Assistant",
        "model": SupervisorEntityModel.OS,
        "sw_version": os_dict[ATTR_VERSION],
        "name": "Home Assistant Operating System",
        "entry_type": ATTR_SERVICE,
    }
    dev_reg.async_get_or_create(**params)


@callback
def async_remove_addons_from_dev_reg(dev_reg: DeviceRegistry, addons: set[str]) -> None:
    """Remove addons from the device registry."""
    for addon_slug in addons:
        if dev := dev_reg.async_get_device({(DOMAIN, addon_slug)}):
            dev_reg.async_remove_device(dev.id)


class HassioDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to retrieve Hass.io status."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, dev_reg: DeviceRegistry
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
        )
        self.data = {}
        self.entry_id = config_entry.entry_id
        self.dev_reg = dev_reg
        self.is_hass_os = "hassos" in get_info(self.hass)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        new_data = {}
        supervisor_info = get_supervisor_info(self.hass)
        store_data = get_store(self.hass)

        repositories = {
            repo[ATTR_SLUG]: repo[ATTR_NAME]
            for repo in store_data.get("repositories", [])
        }

        new_data["addons"] = {
            addon[ATTR_SLUG]: {
                **addon,
                ATTR_REPOSITORY: repositories.get(
                    addon.get(ATTR_REPOSITORY), addon.get(ATTR_REPOSITORY, "")
                ),
            }
            for addon in supervisor_info.get("addons", [])
        }
        if self.is_hass_os:
            new_data["os"] = get_os_info(self.hass)

        # If this is the initial refresh, register all addons and return the dict
        if not self.data:
            async_register_addons_in_dev_reg(
                self.entry_id, self.dev_reg, new_data["addons"].values()
            )
            if self.is_hass_os:
                async_register_os_in_dev_reg(
                    self.entry_id, self.dev_reg, new_data["os"]
                )

        # Remove add-ons that are no longer installed from device registry
        supervisor_addon_devices = {
            list(device.identifiers)[0][1]
            for device in self.dev_reg.devices.values()
            if self.entry_id in device.config_entries
            and device.model == SupervisorEntityModel.ADDON
        }
        if stale_addons := supervisor_addon_devices - set(new_data["addons"]):
            async_remove_addons_from_dev_reg(self.dev_reg, stale_addons)

        # If there are new add-ons, we should reload the config entry so we can
        # create new devices and entities. We can return an empty dict because
        # coordinator will be recreated.
        if self.data and set(new_data["addons"]) - set(self.data["addons"]):
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry_id)
            )
            return {}

        return new_data
