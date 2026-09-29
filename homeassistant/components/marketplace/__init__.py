"""The Marketplace integration.

Handles downloads of custom integrations, dashboard resources, themes,
templates and python scripts from GitHub.
"""

from functools import partial
import os

from aiogithubapi import GitHubAPI, GitHubAuthenticationException, GitHubException
from aiohttp import web
from aiohttp.web_exceptions import HTTPMovedPermanently
from awesomeversion import AwesomeVersion

from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.const import Platform, __version__ as HAVERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_clear_custom_components_cache
from homeassistant.util.hass_dict import HassKey

from .base import MarketplaceConfigEntry, MarketplaceManager
from .const import (
    CLIENT_NAME,
    DOMAIN,
    LEGACY_DASHBOARD_RESOURCE_BASE,
    LEGACY_HACS_SYSTEM_ID,
    RESTART_ISSUE_PREFIX,
)
from .data_client import CatalogClient
from .enums import DisabledReason, LovelaceMode, MarketplaceStage
from .exceptions import MarketplaceError
from .migration import (
    async_adopt_legacy_install,
    async_migrate_dashboard_resources,
    async_remove_duplicate_entries,
    async_remove_legacy_files,
)
from .utils.backup import restore_interrupted_backups
from .utils.data import MarketplaceData
from .utils.file_system import async_exists
from .utils.logger import LOGGER
from .utils.queue_manager import QueueManager
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

    # The custom integration lived at /hacs, where bookmarks still point
    hass.http.register_redirect("/hacs", "/marketplace")
    hass.http.register_view(LegacyPanelRedirectView)

    # A disabled entry counts, turning the Marketplace off is the user's call
    if not hass.config_entries.async_entries(DOMAIN):
        discovery_flow.async_create_flow(
            hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
        )

    return True


@callback
def _async_remove_restart_issues(hass: HomeAssistant) -> None:
    """Remove the restart issues of downloads from before this start.

    Home Assistant just started, so every one of them has been dealt with.
    """
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(RESTART_ISSUE_PREFIX):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def _async_serve_legacy_plugin_path(
    hass: HomeAssistant, lovelace_mode: LovelaceMode
) -> None:
    """Keep serving downloaded plugins on the path the custom integration used.

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
    it here makes the next start serve what the Marketplace downloads into it.
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


async def _async_initialize_integration(
    hass: HomeAssistant,
    config_entry: MarketplaceConfigEntry,
) -> bool:
    """Initialize the integration."""
    config_entry.runtime_data = marketplace = MarketplaceManager()

    marketplace.configuration.update_from_dict(
        {
            "config_entry": config_entry,
            **config_entry.data,
        },
    )

    marketplace.set_stage(None)

    LOGGER.info("Starting the Marketplace")

    clientsession = async_get_clientsession(hass)

    marketplace.version = AwesomeVersion(HAVERSION)
    marketplace.hass = hass
    marketplace.queue = QueueManager(hass=hass)
    marketplace.data = MarketplaceData(marketplace=marketplace)
    marketplace.data_client = CatalogClient(
        session=clientsession,
        client_name=CLIENT_NAME,
    )
    marketplace.session = clientsession

    marketplace.core.lovelace_mode = LovelaceMode(
        hass.data[LOVELACE_DATA].resource_mode
    )
    marketplace.core.config_path = marketplace.hass.config.path()
    marketplace.status.created_www_directory = await _async_ensure_www_directory(hass)
    await _async_serve_legacy_plugin_path(hass, marketplace.core.lovelace_mode)

    # Before anything looks at what is downloaded, a restart during a download
    # can have left the previous content in a backup.
    if await hass.async_add_executor_job(restore_interrupted_backups, marketplace):
        async_clear_custom_components_cache(hass)

    # An empty token keeps aiogithubapi from reading GITHUB_TOKEN from the
    # environment, without a connected account the calls are anonymous.
    marketplace.githubapi = GitHubAPI(
        token=marketplace.configuration.token or "",
        session=clientsession,
        client_name=CLIENT_NAME,
    )

    try:
        if not await marketplace.data.restore():
            raise ConfigEntryNotReady(
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

    # The restore adopts the legacy storage files, only then can they go. Safe
    # and recovery mode are the way back to an older version, that needs them.
    if not hass.config.safe_mode and not hass.config.recovery_mode:
        await async_remove_legacy_files(hass)

    marketplace.set_stage(MarketplaceStage.SETUP)

    # Setting up can leave the Marketplace disabled, an invalid token is for the user
    # to fix, anything else is worth another try.
    if marketplace.system.disabled_reason is DisabledReason.INVALID_TOKEN:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_token"
        )

    if marketplace.system.disabled_reason is not None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key=f"disabled_{marketplace.system.disabled_reason}",
        )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    marketplace.set_stage(MarketplaceStage.WAITING)
    LOGGER.info(
        "Setup complete, waiting for Home Assistant before startup tasks starts"
    )

    config_entry.async_on_unload(
        async_at_start(hass=hass, at_start_cb=marketplace.startup_tasks)
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> bool:
    """Set up this integration using UI."""
    async_adopt_legacy_install(hass, config_entry)
    await async_migrate_dashboard_resources(hass)

    return await _async_initialize_integration(hass=hass, config_entry=config_entry)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> bool:
    """Handle removal of an entry."""
    marketplace = config_entry.runtime_data

    if marketplace.queue.has_pending_tasks:
        LOGGER.warning("Pending tasks, can not unload, try again later")
        return False

    # Clear out pending queue
    marketplace.queue.clear()

    for task in marketplace.recurring_tasks:
        # Cancel all pending tasks
        task()

    # Store data
    await marketplace.data.async_write(force=True)

    if not await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        return False

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

    if marketplace.repositories.is_downloaded(repository_id) and (
        repository := marketplace.repositories.get_by_id(repository_id)
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="repository_still_downloaded",
            translation_placeholders={"repository": repository.data.full_name},
        )

    return True
