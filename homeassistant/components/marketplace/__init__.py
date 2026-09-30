"""The Marketplace integration.

Installs custom integrations, dashboard resources, themes and templates from
GitHub.
"""

import asyncio
import contextlib
from functools import partial
import os

from aiogithubapi import GitHubAuthenticationException, GitHubException
from aiohttp import web
from aiohttp.web_exceptions import HTTPMovedPermanently

from homeassistant.auth import EVENT_USER_REMOVED
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_clear_custom_components_cache
from homeassistant.util.hass_dict import HassKey

from .base import MarketplaceConfigEntry, MarketplaceManager
from .const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    LEGACY_DASHBOARD_RESOURCE_BASE,
    LEGACY_HACS_SYSTEM_ID,
    RESTART_ISSUE_PREFIX,
)
from .enums import DisabledReason, LovelaceMode, MarketplaceStage
from .exceptions import MarketplaceError
from .migration import (
    LEGACY_HACS_DOMAIN,
    async_adopt_legacy_install,
    async_migrate_dashboard_resources,
    async_remove_duplicate_entries,
    async_remove_legacy_files,
)
from .utils.backup import restore_interrupted_backups
from .utils.file_system import async_exists
from .utils.logger import LOGGER
from .utils.storage import STORAGE_CACHE_KEY
from .websocket import async_register_websocket_commands

PLATFORMS = [Platform.SWITCH, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Set once the old plugin path is served, a route can not be removed on reload
DATA_LEGACY_PLUGIN_PATH: HassKey[None] = HassKey(f"{DOMAIN}_legacy_plugin_path")


class LegacyPanelRedirectView(HomeAssistantView):
    """Redirect the paths below the panel of the custom integration."""

    url = "/hacs/{tail:.*}"
    name = "marketplace:legacy_panel_redirect"
    # Bookmarks are opened before there is a session, like the frontend's own
    # redirects.
    requires_auth = False

    async def get(self, request: web.Request, tail: str) -> web.StreamResponse:
        """Redirect to the same path below the Marketplace panel."""
        target = f"/marketplace/{tail}"
        if query_string := request.query_string:
            target = f"{target}?{query_string}"

        raise HTTPMovedPermanently(target)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Marketplace integration."""
    await async_remove_duplicate_entries(hass)
    _async_remove_restart_issues(hass)

    # Registered once per start, the handlers look the loaded entry up themselves
    async_register_websocket_commands(hass)

    # Not tied to the entry, the panel explains a setup that failed. It is
    # reached from the Settings dashboard, so it never shows in the sidebar.
    async_register_built_in_panel(
        hass, DOMAIN, require_admin=True, show_in_sidebar=False
    )

    # The custom integration lived at /hacs, where bookmarks still point
    hass.http.register_redirect("/hacs", "/marketplace")
    hass.http.register_view(LegacyPanelRedirectView)

    # A disabled entry counts, turning the Marketplace off is the user's call.
    # An entry of the custom integration is only left in safe and recovery
    # mode, it is taken over at the next normal start.
    entries = hass.config_entries.async_entries
    if not entries(DOMAIN) and not entries(LEGACY_HACS_DOMAIN):
        discovery_flow.async_create_flow(
            hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
        )

    return True


@callback
def _async_remove_restart_issues(hass: HomeAssistant) -> None:
    """Remove the restart issues of installs from before this start.

    Home Assistant just started, so every one of them has been dealt with.
    """
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(RESTART_ISSUE_PREFIX):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def _async_serve_legacy_plugin_path(
    hass: HomeAssistant, lovelace_mode: LovelaceMode
) -> None:
    """Keep serving installed plugins on the path the custom integration used.

    Dashboards in YAML, and cards that name a URL themselves, still load from it.
    """
    if DATA_LEGACY_PLUGIN_PATH in hass.data:
        return

    plugin_directory = hass.config.path("www/community")
    if not await async_exists(hass, plugin_directory):
        return

    hass.data[DATA_LEGACY_PLUGIN_PATH] = None
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                LEGACY_DASHBOARD_RESOURCE_BASE,
                plugin_directory,
                # Only resources in storage carry a version that changes on update
                cache_headers=lovelace_mode is LovelaceMode.STORAGE,
            )
        ]
    )


async def _async_ensure_www_directory(hass: HomeAssistant) -> bool:
    """Create the www directory when it is missing, return if it was created.

    The frontend only registers /local when www/ exists at startup, so creating
    it here makes the next start serve what the Marketplace installs into it.
    """
    www_directory = hass.config.path("www")
    if await async_exists(hass, www_directory):
        return False

    await hass.async_add_executor_job(
        partial(os.makedirs, www_directory, exist_ok=True)
    )
    LOGGER.info(
        "Created %s, dashboard resources are served after a restart", www_directory
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> bool:
    """Set up the Marketplace from its config entry."""
    async_adopt_legacy_install(hass, config_entry)
    await async_migrate_dashboard_resources(hass)

    config_entry.runtime_data = marketplace = MarketplaceManager(hass, config_entry)
    LOGGER.info("Starting the Marketplace")

    await _async_prepare_config_directory(hass, marketplace)
    await _async_restore(marketplace)

    # The restore adopts the legacy storage files, only then can they go. Safe
    # and recovery mode are the way back to an older version, that needs them.
    if not hass.config.safe_mode and not hass.config.recovery_mode:
        await async_remove_legacy_files(hass)

    marketplace.set_stage(MarketplaceStage.SETUP)
    _raise_when_disabled(marketplace)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    marketplace.set_stage(MarketplaceStage.WAITING)
    LOGGER.info(
        "Setup complete, waiting for Home Assistant before startup tasks starts"
    )
    _async_start_once_started(hass, config_entry)

    await _async_follow_removed_users(hass, config_entry)

    return True


async def _async_prepare_config_directory(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Get the configuration directory ready for what is installed into it."""
    marketplace.status.created_www_directory = await _async_ensure_www_directory(hass)
    await _async_serve_legacy_plugin_path(hass, marketplace.core.lovelace_mode)

    # Before anything looks at what is installed, a restart during an install
    # can have left the previous content in a backup.
    if await hass.async_add_executor_job(restore_interrupted_backups, marketplace):
        async_clear_custom_components_cache(hass)


async def _async_restore(marketplace: MarketplaceManager) -> None:
    """Restore what the Marketplace stored, and what it knows is installed."""
    try:
        # Trying again reads the same file, it takes the user to fix it
        if not await marketplace.data.restore():
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="restore_failed"
            )

        marketplace.set_active_categories()
    except GitHubAuthenticationException as exception:
        if marketplace.github_connected:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_token"
            ) from exception
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"error": str(exception)},
        ) from exception
    except (GitHubException, MarketplaceError) as exception:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"error": str(exception)},
        ) from exception


def _raise_when_disabled(marketplace: MarketplaceManager) -> None:
    """Refuse a setup that left the Marketplace disabled.

    An invalid token is for the user to fix, anything else is worth another try.
    """
    if marketplace.system.disabled_reason is DisabledReason.INVALID_TOKEN:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_token"
        )

    if marketplace.system.disabled_reason is not None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key=f"disabled_{marketplace.system.disabled_reason}",
        )


@callback
def _async_start_once_started(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> None:
    """Run the startup tasks once Home Assistant started, the unload stops them."""
    marketplace = config_entry.runtime_data

    @callback
    def _async_start_tasks(_: HomeAssistant) -> None:
        marketplace.startup_task = config_entry.async_create_task(
            hass, marketplace.startup_tasks(), "marketplace_startup_tasks"
        )

    # The catalog is fetched over the network, Home Assistant does not wait
    # for it to finish starting
    config_entry.async_on_unload(
        async_at_started(hass=hass, at_start_cb=_async_start_tasks)
    )


async def _async_follow_removed_users(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> None:
    """Forget the warning acceptance of every user who is removed.

    Automations install on the word of whoever accepted, not of a removed
    user, also one removed while the Marketplace was not loaded.
    """
    marketplace = config_entry.runtime_data
    users = {user.id for user in await hass.auth.async_get_users()}
    for user_id in list(config_entry.data.get(CONF_WARNING_ACCEPTED, {})):
        if user_id not in users:
            marketplace.async_forget_warning_acceptance(user_id)

    @callback
    def _async_forget_removed_user(event: Event) -> None:
        marketplace.async_forget_warning_acceptance(event.data["user_id"])

    config_entry.async_on_unload(
        hass.bus.async_listen(EVENT_USER_REMOVED, _async_forget_removed_user)
    )


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> bool:
    """Unload the Marketplace, once the installs that run are done."""
    marketplace = config_entry.runtime_data

    # An install writes on its own, a new setup would restore its backup under it
    await marketplace.async_wait_for_installs()

    # Nothing stops before this, a failed unload leaves the Marketplace running
    if not await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        return False

    # Cancelled first, the startup tasks add the recurring ones
    if (startup_task := marketplace.startup_task) is not None:
        startup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await startup_task

    for task in marketplace.recurring_tasks:
        task()

    # A run in flight would carry on with this manager, next to the new one
    for run in list(marketplace.recurring_runs):
        run.cancel()
    await asyncio.gather(*marketplace.recurring_runs, return_exceptions=True)

    # Queued work belongs to this setup, the next one queues its own
    marketplace.queue.clear()

    await marketplace.data.async_write(force=True)

    marketplace.set_stage(None)
    marketplace.disable(DisabledReason.REMOVED)

    hass.data.pop(STORAGE_CACHE_KEY, None)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: MarketplaceConfigEntry,
    device_entry: AnyDeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    marketplace = config_entry.runtime_data
    repository_id = None
    for identifier in device_entry.identifiers:
        if (
            isinstance(identifier, tuple)
            and len(identifier) == 2
            and identifier[0] == DOMAIN
        ):
            repository_id = identifier[1]
            break

    if repository_id is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_without_a_repository",
            translation_placeholders={"device_id": device_entry.id},
        )

    if repository_id == LEGACY_HACS_SYSTEM_ID:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_of_the_marketplace",
        )

    repository = marketplace.repositories.get_by_id(repository_id)
    if repository is not None and repository.data.installed:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="repository_still_installed",
            translation_placeholders={"repository": repository.data.full_name},
        )

    return True
