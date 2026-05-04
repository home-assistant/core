"""Support for Hass.io."""

import asyncio
from dataclasses import replace
from datetime import datetime
import logging
import os
import struct
from typing import Any

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import (
    GreenOptions,
    HomeAssistantOptions,
    SupervisorOptions,
    YellowOptions,
)

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.models import RefreshToken
from homeassistant.components import frontend
from homeassistant.components.homeassistant import async_set_stop_handler
from homeassistant.components.homeassistant.const import DATA_STOP_HANDLER
from homeassistant.components.http import (
    CONF_SERVER_HOST,
    CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE,
)
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    HASSIO_USER_NAME,
    SERVER_PORT,
    Platform,
)
from homeassistant.core import Event, HassJob, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.typing import ConfigType

# config_flow, diagnostics, system_health, and entity platforms are imported to
# ensure other dependencies that wait for hassio are not waiting
# for hassio to import its platforms
# backup is pre-imported to ensure that the backup integration does not load
# it from the event loop
from . import (  # noqa: F401
    backup,
    binary_sensor,
    config_flow,
    diagnostics,
    sensor,
    switch,
    system_health,
    update,
)
from .addon_manager import AddonError, AddonInfo, AddonManager, AddonState
from .addon_panel import async_setup_addon_panel
from .auth import async_setup_auth_view
from .config import HassioConfig
from .const import (
    ADDONS_COORDINATOR,
    DATA_COMPONENT,
    DATA_CONFIG_STORE,
    DATA_HASSIO_HOST,
    DATA_HASSIO_HTTP_CONFIG,
    DATA_HASSIO_SUPERVISOR_USER,
    DATA_KEY_SUPERVISOR_ISSUES,
    DOMAIN,
    HASSIO_MAIN_UPDATE_INTERVAL,
    MAIN_COORDINATOR,
    STATS_COORDINATOR,
)
from .coordinator import (
    HassioAddOnDataUpdateCoordinator,
    HassioMainDataUpdateCoordinator,
    HassioStatsDataUpdateCoordinator,
    get_addons_info,
    get_addons_list,
    get_addons_stats,
    get_core_info,
    get_core_stats,
    get_host_info,
    get_info,
    get_network_info,
    get_os_info,
    get_store,
    get_supervisor_info,
    get_supervisor_stats,
)
from .discovery import async_setup_discovery_view
from .handler import HassIO, async_update_diagnostics, get_supervisor_client
from .http import HassIOView
from .ingress import async_setup_ingress_view
from .issues import SupervisorIssues
from .services import async_setup_services
from .websocket_api import async_load_websocket_api

# Expose the future safe name now so integrations can use it
# All references to addons will eventually be refactored and deprecated
get_apps_list = get_addons_list
__all__ = [
    "AddonError",
    "AddonInfo",
    "AddonManager",
    "AddonState",
    "GreenOptions",
    "SupervisorError",
    "YellowOptions",
    "async_update_diagnostics",
    "get_addons_info",
    "get_addons_list",
    "get_addons_stats",
    "get_apps_list",
    "get_core_info",
    "get_core_stats",
    "get_host_info",
    "get_info",
    "get_network_info",
    "get_os_info",
    "get_store",
    "get_supervisor_client",
    "get_supervisor_info",
    "get_supervisor_stats",
]

_LOGGER = logging.getLogger(__name__)


# If new platforms are added, be sure to import them above
# so we do not make other components that depend on hassio
# wait for the import of the platforms
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH, Platform.UPDATE]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


DEPRECATION_URL = (
    "https://www.home-assistant.io/blog/2025/05/22/"
    "deprecating-core-and-supervised-installation-methods-and-32-bit-systems/"
)


def _is_32_bit() -> bool:
    size = struct.calcsize("P")
    return size * 8 == 32


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
def _check_deprecated_setup(hass: HomeAssistant) -> None:
    """Create issues for deprecated installation types and architectures."""
    os_info = get_os_info(hass)
    info = get_info(hass)
    if os_info is None or info is None:
        return
    is_haos = info.get("hassos") is not None
    board = os_info.get("board")
    arch = info.get("arch", "unknown")
    unsupported_board = board in {"tinker", "odroid-xu4", "rpi2"}
    unsupported_os_on_board = board in {"rpi3", "rpi4"}
    if is_haos and (unsupported_board or unsupported_os_on_board):
        issue_id = "deprecated_os_"
        if unsupported_os_on_board:
            issue_id += "aarch64"
        elif unsupported_board:
            issue_id += "armv7"
        ir.async_create_issue(
            hass,
            "homeassistant",
            issue_id,
            learn_more_url=DEPRECATION_URL,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=issue_id,
            translation_placeholders={
                "installation_guide": "https://www.home-assistant.io/installation/",
            },
        )
    bit32 = _is_32_bit()
    deprecated_architecture = bit32 and not (
        unsupported_board or unsupported_os_on_board
    )
    if not is_haos or deprecated_architecture:
        issue_id = "deprecated"
        if not is_haos:
            issue_id += "_method"
        if deprecated_architecture:
            issue_id += "_architecture"
        ir.async_create_issue(
            hass,
            "homeassistant",
            issue_id,
            learn_more_url=DEPRECATION_URL,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=issue_id,
            translation_placeholders={
                "installation_type": "OS" if is_haos else "Supervised",
                "arch": arch,
            },
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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

    host = os.environ["SUPERVISOR"]
    websession = async_get_clientsession(hass)
    hass.data[DATA_COMPONENT] = HassIO(hass.loop, websession, host)
    hass.data[DATA_HASSIO_HOST] = host
    hass.data[DATA_HASSIO_HTTP_CONFIG] = config.get("http", {})

    async_load_websocket_api(hass)
    hass.http.register_view(HassIOView(host, websession))
    async_setup_services(hass)
    async_setup_discovery_view(hass)
    async_setup_auth_view(hass)
    async_setup_ingress_view(hass)
    frontend.async_register_built_in_panel(hass, "app")

    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    supervisor_client = get_supervisor_client(hass)

    try:
        await supervisor_client.supervisor.ping()
    except SupervisorError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="supervisor_not_connected",
        ) from err

    # Load the store
    config_store = HassioConfig(hass)
    await config_store.load()
    hass.data[DATA_CONFIG_STORE] = config_store

    refresh_token = None
    if (hassio_user := config_store.data.hassio_user) is not None:
        user = await hass.auth.async_get_user(hassio_user)
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
        config_store.update(hassio_user=user.id)

    assert user is not None
    hass.data[DATA_HASSIO_SUPERVISOR_USER] = user

    # Set up coordinators — these can raise ConfigEntryNotReady.
    # Register listeners only after all refreshes succeed to avoid accumulation
    # across retries.
    dev_reg = dr.async_get(hass)

    coordinator = HassioMainDataUpdateCoordinator(hass, entry, dev_reg)
    await coordinator.async_config_entry_first_refresh()
    hass.data[MAIN_COORDINATOR] = coordinator

    addon_coordinator = HassioAddOnDataUpdateCoordinator(
        hass, entry, dev_reg, coordinator.jobs
    )
    await addon_coordinator.async_config_entry_first_refresh()
    hass.data[ADDONS_COORDINATOR] = addon_coordinator

    stats_coordinator = HassioStatsDataUpdateCoordinator(hass, entry)
    await stats_coordinator.async_config_entry_first_refresh()
    hass.data[STATS_COORDINATOR] = stats_coordinator

    # All coordinators refreshed successfully. Start the issues listener and
    # install the stop handler now so they are never left in a partial state
    # if a coordinator refresh raises ConfigEntryNotReady.
    hass.data[DATA_KEY_SUPERVISOR_ISSUES] = issues = SupervisorIssues(hass)

    async def _async_stop(hass: HomeAssistant, restart: bool) -> None:
        """Stop or restart home assistant."""
        if restart:
            await supervisor_client.homeassistant.restart()
        else:
            await supervisor_client.homeassistant.stop()

    # Install a custom handler for the homeassistant.restart / stop services,
    # and restore the previous one when this entry unloads.
    prev_stop_handler = hass.data.get(DATA_STOP_HANDLER)
    async_set_stop_handler(hass, _async_stop)

    def _restore_stop_handler() -> None:
        if prev_stop_handler is not None:
            async_set_stop_handler(hass, prev_stop_handler)
        else:
            hass.data.pop(DATA_STOP_HANDLER, None)

    entry.async_on_unload(_restore_stop_handler)
    last_timezone = None
    last_country = None

    async def push_config(_: Event | None) -> None:
        """Push core config to Hass.io."""
        nonlocal last_timezone
        nonlocal last_country

        new_timezone = hass.config.time_zone
        new_country = hass.config.country

        if new_timezone != last_timezone or new_country != last_country:
            last_timezone = new_timezone
            last_country = new_country

            try:
                await supervisor_client.supervisor.set_options(
                    SupervisorOptions(timezone=new_timezone, country=new_country)
                )
            except SupervisorError as err:
                _LOGGER.warning("Failed to update Supervisor options: %s", err)

    entry.async_on_unload(hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, push_config))

    http_config: dict[str, Any] = hass.data.get(DATA_HASSIO_HTTP_CONFIG, {})

    async def update_hass_api(refresh_token: RefreshToken) -> None:
        """Update Home Assistant API data on Hass.io."""
        options = HomeAssistantOptions(
            ssl=CONF_SSL_CERTIFICATE in http_config,
            port=http_config.get(CONF_SERVER_PORT) or SERVER_PORT,
            refresh_token=refresh_token.token,
        )

        if http_config.get(CONF_SERVER_HOST) is not None:
            options = replace(options, watchdog=False)
            _LOGGER.warning(
                "Found incompatible HTTP option 'server_host'. Watchdog feature"
                " disabled"
            )

        try:
            await supervisor_client.homeassistant.set_options(options)
        except SupervisorError as err:
            _LOGGER.warning(
                "Failed to update Home Assistant options in Supervisor: %s", err
            )

    await asyncio.gather(
        update_hass_api(refresh_token),
        push_config(None),
        issues.setup(),
        async_setup_addon_panel(hass),
    )

    # Setup hardware integration for the detected board type
    @callback
    def _async_setup_hardware_integration(_: datetime | None = None) -> None:
        """Set up hardware integration for the detected board type."""
        if (os_info := get_os_info(hass)) is None:
            # os info not yet fetched from supervisor, retry later
            async_call_later(
                hass,
                HASSIO_MAIN_UPDATE_INTERVAL,
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

    def deprecated_setup_issue() -> None:
        _check_deprecated_setup(hass)
        listener()

    listener = coordinator.async_add_listener(deprecated_setup_issue)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Unload coordinator
    coordinator: HassioMainDataUpdateCoordinator = hass.data[MAIN_COORDINATOR]
    coordinator.unload()

    # Pop coordinators and entry-level data
    hass.data.pop(MAIN_COORDINATOR, None)
    hass.data.pop(ADDONS_COORDINATOR, None)
    hass.data.pop(STATS_COORDINATOR, None)
    hass.data.pop(DATA_CONFIG_STORE, None)
    hass.data.pop(DATA_HASSIO_SUPERVISOR_USER, None)

    if (
        supervisor_issues := hass.data.pop(DATA_KEY_SUPERVISOR_ISSUES, None)
    ) is not None:
        supervisor_issues.unload()

    return unload_ok
