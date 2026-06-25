"""Support for Hass.io."""

import asyncio
from functools import partial
import logging
import os
import struct

from aiohasupervisor import SupervisorBadRequestError, SupervisorError
from aiohasupervisor.models import (
    GreenOptions,
    HomeAssistantOptions,
    SupervisorOptions,
    YellowOptions,
)

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.models import RefreshToken, User
from homeassistant.components import frontend
from homeassistant.components.homeassistant import async_set_stop_handler
from homeassistant.components.onboarding import async_is_onboarded
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, HASSIO_USER_NAME, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
from .config import HassioConfigStore, StoredHassioConfig
from .config_entry import async_get_hassio_entry
from .const import (
    ADDONS_COORDINATOR,
    DATA_COMPONENT,
    DATA_HASSIO_HOST,
    DATA_HASSIO_SUPERVISOR_USER,
    DATA_HASSIO_UPDATE_OPTIONS,
    DATA_KEY_SUPERVISOR_ISSUES,
    DOMAIN,
    ENTRY_DATA_USER,
    MAIN_COORDINATOR,
    OPTION_ADD_ON_BACKUP_BEFORE_UPDATE,
    OPTION_ADD_ON_BACKUP_RETAIN_COPIES,
    OPTION_CORE_BACKUP_BEFORE_UPDATE,
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
from .exceptions import HassioNotReadyError
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
    "HassioNotReadyError",
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


async def _async_get_or_create_supervisor_user(
    hass: HomeAssistant,
    entry: ConfigEntry | None,
    legacy_user_id: str | None = None,
) -> User:
    """Get or create the Supervisor system user."""
    user: User | None = None

    if entry is not None and (entry_user_id := entry.data.get(ENTRY_DATA_USER)):
        user = await hass.auth.async_get_user(entry_user_id)

    if user is None and legacy_user_id is not None:
        user = await hass.auth.async_get_user(legacy_user_id)

    if user is None:
        user = await hass.auth.async_create_system_user(
            HASSIO_USER_NAME, group_ids=[GROUP_ID_ADMIN]
        )
        if entry is not None:
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, ENTRY_DATA_USER: user.id},
            )

    # Migrate old Hass.io users to be admin.
    if not user.is_admin:
        await hass.auth.async_update_user(user, group_ids=[GROUP_ID_ADMIN])

    # Migrate old name
    if user.name == "Hass.io":
        await hass.auth.async_update_user(user, name=HASSIO_USER_NAME)

    return user


@callback
def _async_migrate_legacy_options(
    entry: ConfigEntry, legacy_data: StoredHassioConfig
) -> dict[str, bool | int]:
    """Merge legacy update options into entry options without overriding existing values."""
    if not (legacy_update_config := legacy_data.get("update_config")):
        return {}

    option_updates: dict[str, bool | int] = {}

    if OPTION_ADD_ON_BACKUP_BEFORE_UPDATE not in entry.options:
        option_updates[OPTION_ADD_ON_BACKUP_BEFORE_UPDATE] = legacy_update_config[
            "add_on_backup_before_update"
        ]

    if OPTION_ADD_ON_BACKUP_RETAIN_COPIES not in entry.options:
        option_updates[OPTION_ADD_ON_BACKUP_RETAIN_COPIES] = legacy_update_config[
            "add_on_backup_retain_copies"
        ]

    if OPTION_CORE_BACKUP_BEFORE_UPDATE not in entry.options:
        option_updates[OPTION_CORE_BACKUP_BEFORE_UPDATE] = legacy_update_config[
            "core_backup_before_update"
        ]

    return option_updates


@callback
def _check_deprecated_setup(hass: HomeAssistant) -> None:
    """Create issues for deprecated installation types and architectures."""
    os_info = get_os_info(hass)
    info = get_info(hass)
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

    legacy_store = HassioConfigStore(hass)
    legacy_data = await legacy_store.async_load()

    entry = async_get_hassio_entry(hass)

    legacy_user_id: str | None = None
    if legacy_data is not None:
        legacy_user_id = legacy_data.get("hassio_user")

        if entry is not None:
            data_updates: dict[str, str] = {}
            if ENTRY_DATA_USER not in entry.data and legacy_user_id is not None:
                data_updates[ENTRY_DATA_USER] = legacy_user_id

            option_updates = _async_migrate_legacy_options(entry, legacy_data)

            if data_updates or option_updates:
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, **data_updates},
                    options={**entry.options, **option_updates},
                )

            await legacy_store.async_remove()
        elif legacy_update_config := legacy_data.get("update_config"):
            options: dict[str, bool | int] = {
                OPTION_ADD_ON_BACKUP_BEFORE_UPDATE: legacy_update_config[
                    "add_on_backup_before_update"
                ],
                OPTION_ADD_ON_BACKUP_RETAIN_COPIES: legacy_update_config[
                    "add_on_backup_retain_copies"
                ],
                OPTION_CORE_BACKUP_BEFORE_UPDATE: legacy_update_config[
                    "core_backup_before_update"
                ],
            }
            hass.data[DATA_HASSIO_UPDATE_OPTIONS] = options

    hass.data[DATA_HASSIO_SUPERVISOR_USER] = await _async_get_or_create_supervisor_user(
        hass, entry, legacy_user_id
    )

    async_load_websocket_api(hass)
    hass.http.register_view(HassIOView(host, websession))
    async_setup_services(hass)
    async_setup_discovery_view(hass)
    async_setup_auth_view(hass)
    async_setup_ingress_view(hass)
    async_setup_addon_panel(hass)
    frontend.async_register_built_in_panel(hass, "app")

    if entry is None:
        discovery_flow.async_create_flow(
            hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    if (user := hass.data.get(DATA_HASSIO_SUPERVISOR_USER)) is not None:
        if entry.data.get(ENTRY_DATA_USER) != user.id:
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, ENTRY_DATA_USER: user.id},
            )
    else:
        user = await _async_get_or_create_supervisor_user(hass, entry)

    hass.data[DATA_HASSIO_SUPERVISOR_USER] = user

    supervisor_client = get_supervisor_client(hass)

    try:
        await supervisor_client.supervisor.ping()
    except SupervisorError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="supervisor_not_connected",
        ) from err

    # During onboarding, Supervisor may be out of date. Attempt an update now
    # so that core loads against an up-to-date Supervisor. A
    # SupervisorBadRequestError means there is no update available, proceed
    # normally. No exception means an update was triggered and we must wait for
    # it to complete. Any other SupervisorError means something unexpected went
    # wrong and we cannot proceed right now.
    if not async_is_onboarded(hass):
        try:
            await supervisor_client.supervisor.update()
        except SupervisorBadRequestError:
            pass  # No update available, proceed normally.
        except SupervisorError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="supervisor_not_connected",
            ) from err
        else:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="supervisor_update_pending",
            )

    # Get or create a refresh token for the Supervisor user
    if user.refresh_tokens:
        refresh_token = list(user.refresh_tokens.values())[0]
    else:
        refresh_token = await hass.auth.async_create_refresh_token(user)

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

    def _unload_supervisor_issues() -> None:
        if (
            supervisor_issues := hass.data.pop(DATA_KEY_SUPERVISOR_ISSUES, None)
        ) is not None:
            supervisor_issues.unload()

    entry.async_on_unload(_unload_supervisor_issues)

    async def _async_stop(hass: HomeAssistant, restart: bool) -> None:
        """Stop or restart home assistant."""
        if restart:
            await supervisor_client.homeassistant.restart()
        else:
            await supervisor_client.homeassistant.stop()

    # Install a custom handler for the homeassistant.restart / stop services,
    # and restore the default one when this entry unloads.
    async_set_stop_handler(hass, _async_stop)
    entry.async_on_unload(partial(async_set_stop_handler, hass))

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

    async def update_hass_api(refresh_token: RefreshToken) -> None:
        """Update Home Assistant API data on Hass.io."""
        # hass.config.api is always set here: hassio depends on http, and the
        # http integration assigns hass.config.api during its async_setup.
        assert hass.config.api is not None
        options = HomeAssistantOptions(
            ssl=hass.config.api.use_ssl,
            port=hass.config.api.port,
            refresh_token=refresh_token.token,
        )

        try:
            await supervisor_client.homeassistant.set_options(options)
        except SupervisorError as err:
            _LOGGER.warning(
                "Failed to update Home Assistant options in Supervisor: %s", err
            )

    # Push initial config to Supervisor and start issues listener
    await asyncio.gather(
        update_hass_api(refresh_token), push_config(None), issues.setup()
    )

    # Setup hardware integration for the detected board type
    # This is done after the initial data refresh to ensure that
    # the board info is available.
    os_info = get_os_info(hass)
    if (board := os_info.get("board")) is not None and (
        hw_integration := HARDWARE_INTEGRATIONS.get(board)
    ) is not None:
        discovery_flow.async_create_flow(
            hass, hw_integration, context={"source": SOURCE_SYSTEM}, data={}
        )

    # Check for deprecated setup and create issues if needed.
    # This is done after the initial data refresh to ensure that
    # the info needed is available.
    _check_deprecated_setup(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Pop coordinators and entry-level data
    hass.data.pop(MAIN_COORDINATOR, None)
    hass.data.pop(ADDONS_COORDINATOR, None)
    hass.data.pop(STATS_COORDINATOR, None)

    return unload_ok
