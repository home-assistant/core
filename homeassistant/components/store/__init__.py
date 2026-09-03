"""HACS gives you a powerful UI to handle downloads of all your custom needs.

For more details about this integration, please refer to the documentation at
https://hacs.xyz/
"""

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

from .base import HacsBase, StoreConfigEntry
from .const import CLIENT_NAME, DOMAIN, HACS_SYSTEM_ID
from .data_client import HacsDataClient
from .enums import HacsDisabledReason, HacsStage, LovelaceMode
from .exceptions import HacsException
from .migration import async_migrate_from_hacs, async_remove_duplicate_entries
from .utils.data import HacsData
from .utils.queue_manager import QueueManager
from .utils.store import STORE_CACHE_KEY
from .websocket import async_register_websocket_commands

PLATFORMS = [Platform.SWITCH, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class HacsRedirectView(HomeAssistantView):
    """Redirect the paths below the old HACS panel to the store panel."""

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

    # HACS lived at /hacs, which is what bookmarks and links still point at
    hass.http.register_redirect("/hacs", "/store")
    hass.http.register_view(HacsRedirectView)

    return True


async def _async_initialize_integration(
    hass: HomeAssistant,
    config_entry: StoreConfigEntry,
) -> bool:
    """Initialize the integration."""
    config_entry.runtime_data = hacs = HacsBase()
    hacs.enable_hacs()

    if config_entry.source == SOURCE_IMPORT:
        # Import is not supported
        hass.async_create_task(hass.config_entries.async_remove(config_entry.entry_id))
        return False

    hacs.configuration.update_from_dict(
        {
            "config_entry": config_entry,
            **config_entry.data,
            **config_entry.options,
        },
    )

    hacs.set_stage(None)

    hacs.log.info("Starting Community store")

    clientsession = async_get_clientsession(hass)

    hacs.version = AwesomeVersion(HAVERSION)
    hacs.hass = hass
    hacs.queue = QueueManager(hass=hass)
    hacs.data = HacsData(hacs=hacs)
    hacs.data_client = HacsDataClient(
        session=clientsession,
        client_name=CLIENT_NAME,
    )
    hacs.system.running = True
    hacs.session = clientsession

    hacs.core.lovelace_mode = LovelaceMode(hass.data[LOVELACE_DATA].resource_mode)
    hacs.core.config_path = hacs.hass.config.path()

    hacs.core.ha_version = AwesomeVersion(HAVERSION)

    # Legacy GitHub client
    hacs.github = GitHub(
        hacs.configuration.token,
        clientsession,
        headers={
            "User-Agent": CLIENT_NAME,
            "Accept": ACCEPT_HEADERS["preview"],
        },
    )

    # New GitHub client
    hacs.githubapi = GitHubAPI(
        token=hacs.configuration.token,
        session=clientsession,
        client_name=CLIENT_NAME,
    )

    hacs.enable_hacs()

    try:
        if not await hacs.data.restore():
            raise ConfigEntryNotReady("Could not restore the stored data")

        hacs.set_active_categories()

        async_register_websocket_commands(hass)
        await hacs.async_setup_frontend_endpoint_plugin()
    except GitHubAuthenticationException as exception:
        raise ConfigEntryAuthFailed(
            "The GitHub token is no longer valid"
        ) from exception
    except (AIOGitHubAPIException, HacsException) as exception:
        raise ConfigEntryNotReady(
            f"Could not set up the Community store: {exception}"
        ) from exception

    hacs.set_stage(HacsStage.SETUP)

    # Setting up can leave the store disabled, an invalid token is for the user
    # to fix, anything else is worth another try.
    if hacs.system.disabled_reason is HacsDisabledReason.INVALID_TOKEN:
        raise ConfigEntryAuthFailed("The GitHub token is no longer valid")

    if hacs.system.disabled:
        raise ConfigEntryNotReady(
            f"The Community store is disabled: {hacs.system.disabled_reason}"
        )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    hacs.set_stage(HacsStage.WAITING)
    hacs.log.info(
        "Setup complete, waiting for Home Assistant before startup tasks starts"
    )

    async_at_start(hass=hass, at_start_cb=hacs.startup_tasks)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: StoreConfigEntry
) -> bool:
    """Set up this integration using UI."""
    # Runs before the update listener is added, trimming the options must not
    # trigger a reload while the entry is still being set up.
    async_migrate_from_hacs(hass, config_entry)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    return await _async_initialize_integration(hass=hass, config_entry=config_entry)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: StoreConfigEntry
) -> bool:
    """Handle removal of an entry."""
    hacs = config_entry.runtime_data

    if hacs.queue.has_pending_tasks:
        hacs.log.warning("Pending tasks, can not unload, try again later.")
        return False

    # Clear out pending queue
    hacs.queue.clear()

    for task in hacs.recurring_tasks:
        # Cancel all pending tasks
        task()

    # Store data
    await hacs.data.async_write(force=True)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hacs.set_stage(None)
    hacs.disable_hacs(HacsDisabledReason.REMOVED)

    hass.data.pop(STORE_CACHE_KEY, None)

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
    hacs = config_entry.runtime_data
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

    if repository_id == HACS_SYSTEM_ID:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_of_the_store",
        )

    if hacs.repositories.is_downloaded(repository_id) and (
        repository := hacs.repositories.get_by_id(repository_id)
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="repository_still_downloaded",
            translation_placeholders={"repository": repository.data.full_name},
        )

    return True
