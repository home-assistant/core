"""The Marketplace integration.

Handles downloads of custom integrations, dashboard resources, themes,
templates, python scripts and AppDaemon apps from GitHub.
"""

from functools import partial
import os

from aiogithubapi import GitHubAPI, GitHubAuthenticationException, GitHubException
from aiohttp import web
from aiohttp.web_exceptions import HTTPMovedPermanently
from awesomeversion import AwesomeVersion

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.const import Platform, __version__ as HAVERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType

from .base import MarketplaceConfigEntry, MarketplaceManager
from .const import CLIENT_NAME, DOMAIN, LEGACY_HACS_SYSTEM_ID
from .data_client import CatalogClient
from .enums import DisabledReason, LovelaceMode, MarketplaceStage
from .exceptions import MarketplaceError
from .migration import (
    async_adopt_legacy_install,
    async_migrate_dashboard_resources,
    async_remove_duplicate_entries,
    async_remove_legacy_files,
)
from .utils.data import MarketplaceData
from .utils.file_system import async_exists
from .utils.logger import LOGGER
from .utils.queue_manager import QueueManager
from .utils.storage import STORAGE_CACHE_KEY
from .websocket import async_register_websocket_commands

PLATFORMS = [Platform.SWITCH, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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

    # Registered once per start, the handlers look the loaded entry up themselves
    async_register_websocket_commands(hass)

    # The custom integration lived at /hacs, where bookmarks still point
    hass.http.register_redirect("/hacs", "/marketplace")
    hass.http.register_view(LegacyPanelRedirectView)

    return True


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
            **config_entry.options,
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

    marketplace.githubapi = GitHubAPI(
        token=marketplace.configuration.token,
        session=clientsession,
        client_name=CLIENT_NAME,
    )

    try:
        if not await marketplace.data.restore():
            raise ConfigEntryNotReady("Could not restore the stored data")

        marketplace.set_active_categories()
    except GitHubAuthenticationException as exception:
        raise ConfigEntryAuthFailed(
            "The GitHub token is no longer valid"
        ) from exception
    except (GitHubException, MarketplaceError) as exception:
        raise ConfigEntryNotReady(
            f"Could not set up the Marketplace: {exception}"
        ) from exception

    # The restore adopts the legacy storage files, only then can they go
    await async_remove_legacy_files(hass)

    marketplace.set_stage(MarketplaceStage.SETUP)

    # Setting up can leave the Marketplace disabled, an invalid token is for the user
    # to fix, anything else is worth another try.
    if marketplace.system.disabled_reason is DisabledReason.INVALID_TOKEN:
        raise ConfigEntryAuthFailed("The GitHub token is no longer valid")

    if marketplace.system.disabled:
        raise ConfigEntryNotReady(
            f"The Marketplace is disabled: {marketplace.system.disabled_reason}"
        )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    marketplace.set_stage(MarketplaceStage.WAITING)
    LOGGER.info(
        "Setup complete, waiting for Home Assistant before startup tasks starts"
    )

    async_at_start(hass=hass, at_start_cb=marketplace.startup_tasks)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> bool:
    """Set up this integration using UI."""
    # Runs before the update listener is added, trimming the options must not
    # trigger a reload while the entry is still being set up.
    async_adopt_legacy_install(hass, config_entry)
    await async_migrate_dashboard_resources(hass)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
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

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    marketplace.set_stage(None)
    marketplace.disable(DisabledReason.REMOVED)

    hass.data.pop(STORAGE_CACHE_KEY, None)

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, config_entry: MarketplaceConfigEntry
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)


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
