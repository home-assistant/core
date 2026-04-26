"""Support for Hass.io."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
import logging
import os
import struct
from typing import Any, cast

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import (
    GreenOptions,
    HomeAssistantInfo,
    HomeAssistantOptions,
    HostInfo,
    InstalledAddon,
    NetworkInfo,
    OSInfo,
    RootInfo,
    StoreInfo,
    SupervisorInfo,
    SupervisorOptions,
    YellowOptions,
)

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.models import RefreshToken
from homeassistant.components import frontend
from homeassistant.components.homeassistant import async_set_stop_handler
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
from homeassistant.util.async_ import create_eager_task

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
    DATA_ADDONS_LIST,
    DATA_COMPONENT,
    DATA_CONFIG_STORE,
    DATA_CORE_INFO,
    DATA_HOST_INFO,
    DATA_INFO,
    DATA_KEY_SUPERVISOR_ISSUES,
    DATA_NETWORK_INFO,
    DATA_OS_INFO,
    DATA_STORE,
    DATA_SUPERVISOR_INFO,
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

    async_load_websocket_api(hass)
    frontend.async_register_built_in_panel(hass, "app")

    host = os.environ["SUPERVISOR"]
    websession = async_get_clientsession(hass)
    hass.data[DATA_COMPONENT] = HassIO(hass.loop, websession, host)
    supervisor_client = get_supervisor_client(hass)

    try:
        await supervisor_client.supervisor.ping()
    except SupervisorError:
        _LOGGER.warning("Not connected with the supervisor / system too busy!")

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

    hass.http.register_view(HassIOView(host, websession))

    async def update_hass_api(http_config: dict[str, Any], refresh_token: RefreshToken):
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

    update_hass_api_task = hass.async_create_task(
        update_hass_api(config.get("http", {}), refresh_token), eager_start=True
    )

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

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, push_config)

    push_config_task = hass.async_create_task(push_config(None), eager_start=True)
    # Start listening for problems with supervisor and making issues
    hass.data[DATA_KEY_SUPERVISOR_ISSUES] = issues = SupervisorIssues(hass)
    issues_task = hass.async_create_task(issues.setup(), eager_start=True)

    # Register services
    async_setup_services(hass, supervisor_client)

    async def update_info_data(_: datetime | None = None) -> None:
        """Update last available supervisor information."""
        supervisor_client = get_supervisor_client(hass)

        try:
            (
                root_info,
                host_info,
                store_info,
                homeassistant_info,
                supervisor_info,
                os_info,
                network_info,
                addons_list,
            ) = cast(
                tuple[
                    RootInfo,
                    HostInfo,
                    StoreInfo,
                    HomeAssistantInfo,
                    SupervisorInfo,
                    OSInfo,
                    NetworkInfo,
                    list[InstalledAddon],
                ],
                await asyncio.gather(
                    create_eager_task(supervisor_client.info()),
                    create_eager_task(supervisor_client.host.info()),
                    create_eager_task(supervisor_client.store.info()),
                    create_eager_task(supervisor_client.homeassistant.info()),
                    create_eager_task(supervisor_client.supervisor.info()),
                    create_eager_task(supervisor_client.os.info()),
                    create_eager_task(supervisor_client.network.info()),
                    create_eager_task(supervisor_client.addons.list()),
                ),
            )

        except SupervisorError as err:
            _LOGGER.warning("Can't read Supervisor data: %s", err)
        else:
            hass.data[DATA_INFO] = root_info
            hass.data[DATA_HOST_INFO] = host_info
            hass.data[DATA_STORE] = store_info
            hass.data[DATA_CORE_INFO] = homeassistant_info
            hass.data[DATA_SUPERVISOR_INFO] = supervisor_info
            hass.data[DATA_OS_INFO] = os_info
            hass.data[DATA_NETWORK_INFO] = network_info
            hass.data[DATA_ADDONS_LIST] = addons_list

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
    async_setup_discovery_view(hass)

    # Init auth Hass.io feature
    assert user is not None
    async_setup_auth_view(hass, user)

    # Init ingress Hass.io feature
    async_setup_ingress_view(hass, host)

    # Init add-on ingress panels
    panels_task = hass.async_create_task(
        async_setup_addon_panel(hass), eager_start=True
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
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
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

    def deprecated_setup_issue() -> None:
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

    # Pop coordinators
    hass.data.pop(MAIN_COORDINATOR, None)
    hass.data.pop(ADDONS_COORDINATOR, None)
    hass.data.pop(STATS_COORDINATOR, None)

    return unload_ok
