"""Support for Hass.io."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime
from functools import partial
import logging
import os
import re
from typing import Any, NamedTuple

from aiohasupervisor import SupervisorError
import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components import panel_custom
from homeassistant.components.homeassistant import async_set_stop_handler
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    EVENT_CORE_CONFIG_UPDATE,
    HASSIO_USER_NAME,
    Platform,
)
from homeassistant.core import (
    Event,
    HassJob,
    HomeAssistant,
    ServiceCall,
    async_get_hass_or_none,
    callback,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    deprecated_function,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.hassio import (
    get_supervisor_ip as _get_supervisor_ip,
    is_hassio as _is_hassio,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service_info.hassio import (
    HassioServiceInfo as _HassioServiceInfo,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.dt import now

# config_flow, diagnostics, system_health, and entity platforms are imported to
# ensure other dependencies that wait for hassio are not waiting
# for hassio to import its platforms
from . import (  # noqa: F401
    binary_sensor,
    config_flow,
    diagnostics,
    sensor,
    system_health,
    update,
)
from .addon_manager import AddonError, AddonInfo, AddonManager, AddonState  # noqa: F401
from .addon_panel import async_setup_addon_panel
from .auth import async_setup_auth_view
from .const import (
    ADDONS_COORDINATOR,
    ATTR_ADDON,
    ATTR_ADDONS,
    ATTR_COMPRESSED,
    ATTR_FOLDERS,
    ATTR_HOMEASSISTANT,
    ATTR_HOMEASSISTANT_EXCLUDE_DATABASE,
    ATTR_INPUT,
    ATTR_LOCATION,
    ATTR_PASSWORD,
    ATTR_SLUG,
    DATA_CORE_INFO,
    DATA_HOST_INFO,
    DATA_INFO,
    DATA_KEY_SUPERVISOR_ISSUES,
    DATA_NETWORK_INFO,
    DATA_OS_INFO,
    DATA_STORE,
    DATA_SUPERVISOR_INFO,
    DOMAIN,
    HASSIO_UPDATE_INTERVAL,
)
from .coordinator import (
    HassioDataUpdateCoordinator,
    get_addons_changelogs,  # noqa: F401
    get_addons_info,
    get_addons_stats,  # noqa: F401
    get_core_info,  # noqa: F401
    get_core_stats,  # noqa: F401
    get_host_info,  # noqa: F401
    get_info,  # noqa: F401
    get_issues_info,  # noqa: F401
    get_os_info,
    get_supervisor_info,  # noqa: F401
    get_supervisor_stats,  # noqa: F401
)
from .discovery import async_setup_discovery_view  # noqa: F401
from .handler import (  # noqa: F401
    HassIO,
    HassioAPIError,
    async_create_backup,
    async_get_green_settings,
    async_get_yellow_settings,
    async_reboot_host,
    async_set_green_settings,
    async_set_yellow_settings,
    async_update_diagnostics,
    get_supervisor_client,
)
from .http import HassIOView
from .ingress import async_setup_ingress_view
from .issues import SupervisorIssues
from .websocket_api import async_load_websocket_api

_LOGGER = logging.getLogger(__name__)

get_supervisor_ip = deprecated_function(
    "homeassistant.helpers.hassio.get_supervisor_ip", breaks_in_ha_version="2025.11"
)(_get_supervisor_ip)
_DEPRECATED_HassioServiceInfo = DeprecatedConstant(
    _HassioServiceInfo,
    "homeassistant.helpers.service_info.hassio.HassioServiceInfo",
    "2025.11",
)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
# If new platforms are added, be sure to import them above
# so we do not make other components that depend on hassio
# wait for the import of the platforms
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.UPDATE]

CONF_FRONTEND_REPO = "development_repo"

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.Schema({vol.Optional(CONF_FRONTEND_REPO): cv.isdir})},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_ADDON_START = "addon_start"
SERVICE_ADDON_STOP = "addon_stop"
SERVICE_ADDON_RESTART = "addon_restart"
SERVICE_ADDON_UPDATE = "addon_update"
SERVICE_ADDON_STDIN = "addon_stdin"
SERVICE_HOST_SHUTDOWN = "host_shutdown"
SERVICE_HOST_REBOOT = "host_reboot"
SERVICE_BACKUP_FULL = "backup_full"
SERVICE_BACKUP_PARTIAL = "backup_partial"
SERVICE_RESTORE_FULL = "restore_full"
SERVICE_RESTORE_PARTIAL = "restore_partial"

VALID_ADDON_SLUG = vol.Match(re.compile(r"^[-_.A-Za-z0-9]+$"))


def valid_addon(value: Any) -> str:
    """Validate value is a valid addon slug."""
    value = VALID_ADDON_SLUG(value)
    hass = async_get_hass_or_none()

    if hass and (addons := get_addons_info(hass)) is not None and value not in addons:
        raise vol.Invalid("Not a valid add-on slug")
    return value


SCHEMA_NO_DATA = vol.Schema({})

SCHEMA_ADDON = vol.Schema({vol.Required(ATTR_ADDON): valid_addon})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend(
    {vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)}
)

SCHEMA_BACKUP_FULL = vol.Schema(
    {
        vol.Optional(
            ATTR_NAME, default=lambda: now().strftime("%Y-%m-%d %H:%M:%S")
        ): cv.string,
        vol.Optional(ATTR_PASSWORD): cv.string,
        vol.Optional(ATTR_COMPRESSED): cv.boolean,
        vol.Optional(ATTR_LOCATION): vol.All(
            cv.string, lambda v: None if v == "/backup" else v
        ),
        vol.Optional(ATTR_HOMEASSISTANT_EXCLUDE_DATABASE): cv.boolean,
    }
)

SCHEMA_BACKUP_PARTIAL = SCHEMA_BACKUP_FULL.extend(
    {
        vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [VALID_ADDON_SLUG]),
    }
)

SCHEMA_RESTORE_FULL = vol.Schema(
    {
        vol.Required(ATTR_SLUG): cv.slug,
        vol.Optional(ATTR_PASSWORD): cv.string,
    }
)

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend(
    {
        vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [VALID_ADDON_SLUG]),
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
}

HARDWARE_INTEGRATIONS = {
    "green": "homeassistant_green",
    "odroid-c2": "hardkernel",
    "odroid-c4": "hardkernel",
    "odroid-m1": "hardkernel",
    "odroid-m1s": "hardkernel",
    "odroid-n2": "hardkernel",
    "odroid-xu4": "hardkernel",
    "rpi2": "raspberry_pi",
    "rpi3": "raspberry_pi",
    "rpi3-64": "raspberry_pi",
    "rpi4": "raspberry_pi",
    "rpi4-64": "raspberry_pi",
    "rpi5-64": "raspberry_pi",
    "yellow": "homeassistant_yellow",
}


def hostname_from_addon_slug(addon_slug: str) -> str:
    """Return hostname of add-on."""
    return addon_slug.replace("_", "-")


@callback
@deprecated_function(
    "homeassistant.helpers.hassio.is_hassio", breaks_in_ha_version="2025.11"
)
@bind_hass
def is_hassio(hass: HomeAssistant) -> bool:
    """Return true if Hass.io is loaded.

    Async friendly.
    """
    return _is_hassio(hass)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: C901
    """Set up the Hass.io component."""
    # Check local setup
    for env in ("SUPERVISOR", "SUPERVISOR_TOKEN"):
        if os.environ.get(env):
            continue
        _LOGGER.error("Missing %s environment variable", env)
        if config_entries := hass.config_entries.async_entries(DOMAIN):
            hass.async_create_task(
                hass.config_entries.async_remove(config_entries[0].entry_id)
            )
        return False

    async_load_websocket_api(hass)

    host = os.environ["SUPERVISOR"]
    websession = async_get_clientsession(hass)
    hass.data[DOMAIN] = hassio = HassIO(hass.loop, websession, host)
    supervisor_client = get_supervisor_client(hass)

    try:
        await supervisor_client.supervisor.ping()
    except SupervisorError:
        _LOGGER.warning("Not connected with the supervisor / system too busy!")

    store = Store[dict[str, str]](hass, STORAGE_VERSION, STORAGE_KEY)
    if (data := await store.async_load()) is None:
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
                await hass.auth.async_update_user(user, name=HASSIO_USER_NAME)

    if refresh_token is None:
        user = await hass.auth.async_create_system_user(
            HASSIO_USER_NAME, group_ids=[GROUP_ID_ADMIN]
        )
        refresh_token = await hass.auth.async_create_refresh_token(user)
        data["hassio_user"] = user.id
        await store.async_save(data)

    # This overrides the normal API call that would be forwarded
    development_repo = config.get(DOMAIN, {}).get(CONF_FRONTEND_REPO)
    if development_repo is not None:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/api/hassio/app",
                    os.path.join(development_repo, "hassio/build"),
                    False,
                )
            ]
        )

    hass.http.register_view(HassIOView(host, websession))

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="hassio",
        webcomponent_name="hassio-main",
        js_url="/api/hassio/app/entrypoint.js",
        embed_iframe=True,
        require_admin=True,
    )

    update_hass_api_task = hass.async_create_task(
        hassio.update_hass_api(config.get("http", {}), refresh_token), eager_start=True
    )

    last_timezone = None

    async def push_config(_: Event | None) -> None:
        """Push core config to Hass.io."""
        nonlocal last_timezone

        new_timezone = str(hass.config.time_zone)

        if new_timezone == last_timezone:
            return

        last_timezone = new_timezone
        await hassio.update_hass_timezone(new_timezone)

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, push_config)

    push_config_task = hass.async_create_task(push_config(None), eager_start=True)
    # Start listening for problems with supervisor and making issues
    hass.data[DATA_KEY_SUPERVISOR_ISSUES] = issues = SupervisorIssues(hass, hassio)
    issues_task = hass.async_create_task(issues.setup(), eager_start=True)

    async def async_service_handler(service: ServiceCall) -> None:
        """Handle service calls for Hass.io."""
        if service.service == SERVICE_ADDON_UPDATE:
            async_create_issue(
                hass,
                DOMAIN,
                "update_service_deprecated",
                breaks_in_ha_version="2025.5",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="update_service_deprecated",
            )
        api_endpoint = MAP_SERVICE_API[service.service]

        data = service.data.copy()
        addon = data.pop(ATTR_ADDON, None)
        slug = data.pop(ATTR_SLUG, None)
        payload = None

        # Pass data to Hass.io API
        if service.service == SERVICE_ADDON_STDIN:
            payload = data[ATTR_INPUT]
        elif api_endpoint.pass_data:
            payload = data

        # Call API
        # The exceptions are logged properly in hassio.send_command
        with suppress(HassioAPIError):
            await hassio.send_command(
                api_endpoint.command.format(addon=addon, slug=slug),
                payload=payload,
                timeout=api_endpoint.timeout,
            )

    for service, settings in MAP_SERVICE_API.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=settings.schema
        )

    async def update_info_data(_: datetime | None = None) -> None:
        """Update last available supervisor information."""
        supervisor_client = get_supervisor_client(hass)

        try:
            (
                hass.data[DATA_INFO],
                hass.data[DATA_HOST_INFO],
                store_info,
                hass.data[DATA_CORE_INFO],
                hass.data[DATA_SUPERVISOR_INFO],
                hass.data[DATA_OS_INFO],
                hass.data[DATA_NETWORK_INFO],
            ) = await asyncio.gather(
                create_eager_task(hassio.get_info()),
                create_eager_task(hassio.get_host_info()),
                create_eager_task(supervisor_client.store.info()),
                create_eager_task(hassio.get_core_info()),
                create_eager_task(hassio.get_supervisor_info()),
                create_eager_task(hassio.get_os_info()),
                create_eager_task(hassio.get_network_info()),
            )

        except HassioAPIError as err:
            _LOGGER.warning("Can't read Supervisor data: %s", err)
        else:
            hass.data[DATA_STORE] = store_info.to_dict()

        async_call_later(
            hass,
            HASSIO_UPDATE_INTERVAL,
            HassJob(update_info_data, cancel_on_shutdown=True),
        )

    # Fetch data
    update_info_task = hass.async_create_task(update_info_data(), eager_start=True)

    async def _async_stop(hass: HomeAssistant, restart: bool) -> None:
        """Stop or restart home assistant."""
        if restart:
            await supervisor_client.homeassistant.restart()
        else:
            await supervisor_client.homeassistant.stop()

    # Set a custom handler for the homeassistant.restart and homeassistant.stop services
    async_set_stop_handler(hass, _async_stop)

    # Init discovery Hass.io feature
    async_setup_discovery_view(hass, hassio)

    # Init auth Hass.io feature
    assert user is not None
    async_setup_auth_view(hass, user)

    # Init ingress Hass.io feature
    async_setup_ingress_view(hass, host)

    # Init add-on ingress panels
    panels_task = hass.async_create_task(
        async_setup_addon_panel(hass, hassio), eager_start=True
    )

    # Make sure to await the update_info task before
    # _async_setup_hardware_integration is called
    # so the hardware integration can be set up
    # and does not fallback to calling later
    await update_hass_api_task
    await panels_task
    await update_info_task
    await push_config_task
    await issues_task

    # Setup hardware integration for the detected board type
    @callback
    def _async_setup_hardware_integration(_: datetime | None = None) -> None:
        """Set up hardware integration for the detected board type."""
        if (os_info := get_os_info(hass)) is None:
            # os info not yet fetched from supervisor, retry later
            async_call_later(
                hass,
                HASSIO_UPDATE_INTERVAL,
                async_setup_hardware_integration_job,
            )
            return
        if (board := os_info.get("board")) is None:
            return
        if (hw_integration := HARDWARE_INTEGRATIONS.get(board)) is None:
            return
        discovery_flow.async_create_flow(
            hass, hw_integration, context={"source": SOURCE_SYSTEM}, data={}
        )

    async_setup_hardware_integration_job = HassJob(
        _async_setup_hardware_integration, cancel_on_shutdown=True
    )

    _async_setup_hardware_integration()
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    dev_reg = dr.async_get(hass)
    coordinator = HassioDataUpdateCoordinator(hass, entry, dev_reg)
    await coordinator.async_config_entry_first_refresh()
    hass.data[ADDONS_COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Pop add-on data
    hass.data.pop(ADDONS_COORDINATOR, None)

    return unload_ok


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
