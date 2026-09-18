"""The Community store integration.

Handles downloads of custom integrations, dashboard resources, themes,
templates, python scripts and AppDaemon apps from GitHub.
"""

from functools import partial
import os

from aiogithubapi import (
    AIOGitHubAPIException,
    GitHub,
    GitHubAPI,
    GitHubAuthenticationException,
)
from aiogithubapi.const import ACCEPT_HEADERS
from aiohttp import web
from aiohttp.web_exceptions import HTTPMovedPermanently
from awesomeversion import AwesomeVersion

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.config_entries import SOURCE_IMPORT
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

from .base import StoreConfigEntry, StoreManager
from .const import CLIENT_NAME, DOMAIN, LEGACY_HACS_SYSTEM_ID
from .data_client import CatalogClient
from .enums import DisabledReason, LovelaceMode, StoreStage
from .exceptions import StoreError
from .migration import (
    async_adopt_legacy_install,
    async_migrate_dashboard_resources,
    async_remove_duplicate_entries,
)
from .utils.data import StoreData
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
    name = "hacs:redirect"
    # Bookmarks are opened before there is a session, like the frontend's own
    # redirects.
    requires_auth = False

    async def get(self, request: web.Request, tail: str) -> web.StreamResponse:
        """Redirect to the same path below the store panel."""
        target = f"/store/{tail}"
        if query_string := request.query_string:
            target = f"{target}?{query_string}"

        raise HTTPMovedPermanently(target)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Community store integration."""
    await async_remove_duplicate_entries(hass)

    # The custom integration lived at /hacs, where bookmarks still point
    hass.http.register_redirect("/hacs", "/store")
    hass.http.register_view(LegacyPanelRedirectView)

    return True


async def _async_ensure_www_directory(hass: HomeAssistant) -> bool:
    """Create the www directory when it is missing, return if it was created.

    The frontend only registers /local when www/ exists at startup, so creating
    it here makes the next start serve what the store downloads into it.
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
    config_entry: StoreConfigEntry,
) -> bool:
    """Initialize the integration."""
    config_entry.runtime_data = store = StoreManager()
    store.enable()

    if config_entry.source == SOURCE_IMPORT:
        # Import is not supported
        hass.async_create_task(hass.config_entries.async_remove(config_entry.entry_id))
        return False

    store.configuration.update_from_dict(
        {
            "config_entry": config_entry,
            **config_entry.data,
            **config_entry.options,
        },
    )

    store.set_stage(None)

    LOGGER.info("Starting Community store")

    clientsession = async_get_clientsession(hass)

    store.version = AwesomeVersion(HAVERSION)
    store.hass = hass
    store.queue = QueueManager(hass=hass)
    store.data = StoreData(store=store)
    store.data_client = CatalogClient(
        session=clientsession,
        client_name=CLIENT_NAME,
    )
    store.system.running = True
    store.session = clientsession

    store.core.lovelace_mode = LovelaceMode(hass.data[LOVELACE_DATA].resource_mode)
    store.core.config_path = store.hass.config.path()
    store.status.created_www_directory = await _async_ensure_www_directory(hass)

    store.core.ha_version = AwesomeVersion(HAVERSION)

    # Legacy GitHub client
    store.github = GitHub(
        store.configuration.token,
        clientsession,
        headers={
            "User-Agent": CLIENT_NAME,
            "Accept": ACCEPT_HEADERS["preview"],
        },
    )

    # New GitHub client
    store.githubapi = GitHubAPI(
        token=store.configuration.token,
        session=clientsession,
        client_name=CLIENT_NAME,
    )

    store.enable()

    try:
        if not await store.data.restore():
            raise ConfigEntryNotReady("Could not restore the stored data")

        store.set_active_categories()

        async_register_websocket_commands(hass)
    except GitHubAuthenticationException as exception:
        raise ConfigEntryAuthFailed(
            "The GitHub token is no longer valid"
        ) from exception
    except (AIOGitHubAPIException, StoreError) as exception:
        raise ConfigEntryNotReady(
            f"Could not set up the Community store: {exception}"
        ) from exception

    store.set_stage(StoreStage.SETUP)

    # Setting up can leave the store disabled, an invalid token is for the user
    # to fix, anything else is worth another try.
    if store.system.disabled_reason is DisabledReason.INVALID_TOKEN:
        raise ConfigEntryAuthFailed("The GitHub token is no longer valid")

    if store.system.disabled:
        raise ConfigEntryNotReady(
            f"The Community store is disabled: {store.system.disabled_reason}"
        )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    store.set_stage(StoreStage.WAITING)
    LOGGER.info(
        "Setup complete, waiting for Home Assistant before startup tasks starts"
    )

    async_at_start(hass=hass, at_start_cb=store.startup_tasks)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: StoreConfigEntry
) -> bool:
    """Set up this integration using UI."""
    # Runs before the update listener is added, trimming the options must not
    # trigger a reload while the entry is still being set up.
    async_adopt_legacy_install(hass, config_entry)
    await async_migrate_dashboard_resources(hass)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    return await _async_initialize_integration(hass=hass, config_entry=config_entry)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: StoreConfigEntry
) -> bool:
    """Handle removal of an entry."""
    store = config_entry.runtime_data

    if store.queue.has_pending_tasks:
        LOGGER.warning("Pending tasks, can not unload, try again later")
        return False

    # Clear out pending queue
    store.queue.clear()

    for task in store.recurring_tasks:
        # Cancel all pending tasks
        task()

    # Store data
    await store.data.async_write(force=True)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    store.set_stage(None)
    store.disable(DisabledReason.REMOVED)

    hass.data.pop(STORAGE_CACHE_KEY, None)

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, config_entry: StoreConfigEntry
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: StoreConfigEntry,
    device_entry: AnyDeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    store = config_entry.runtime_data
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
            translation_key="device_of_the_store",
        )

    if store.repositories.is_downloaded(repository_id) and (
        repository := store.repositories.get_by_id(repository_id)
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="repository_still_downloaded",
            translation_placeholders={"repository": repository.data.full_name},
        )

    return True
