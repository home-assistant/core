"""HACS gives you a powerful UI to handle downloads of all your custom needs.

For more details about this integration, please refer to the documentation at
https://hacs.xyz/
"""

from aiogithubapi import AIOGitHubAPIException, GitHub, GitHubAPI
from aiogithubapi.const import ACCEPT_HEADERS
from awesomeversion import AwesomeVersion

from homeassistant.components.frontend import async_panel_exists, async_remove_panel
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform, __version__ as HAVERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_start

from .base import HacsBase
from .const import CLIENT_NAME, DOMAIN, HACS_SYSTEM_ID
from .data_client import HacsDataClient
from .enums import HacsDisabledReason, HacsStage, LovelaceMode
from .frontend import async_register_frontend
from .utils.data import HacsData
from .utils.queue_manager import QueueManager
from .utils.store import STORE_CACHE_KEY
from .websocket import async_register_websocket_commands

PLATFORMS = [Platform.SWITCH, Platform.UPDATE]


async def _async_initialize_integration(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Initialize the integration."""
    hass.data[DOMAIN] = hacs = HacsBase()
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

    if hacs.core.ha_version is None:
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

    async def async_startup():
        """HACS startup tasks."""
        hacs.enable_hacs()

        if not await hacs.data.restore():
            hacs.disable_hacs(HacsDisabledReason.RESTORE)
            return False

        hacs.set_active_categories()

        async_register_websocket_commands(hass)
        await async_register_frontend(hass, hacs)

        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

        hacs.set_stage(HacsStage.SETUP)
        if hacs.system.disabled:
            return False

        hacs.set_stage(HacsStage.WAITING)
        hacs.log.info(
            "Setup complete, waiting for Home Assistant before startup tasks starts"
        )

        # Schedule startup tasks
        async_at_start(hass=hass, at_start_cb=hacs.startup_tasks)

        return not hacs.system.disabled

    async def async_try_startup(_=None):
        """Startup wrapper for yaml config."""
        try:
            startup_result = await async_startup()
        except AIOGitHubAPIException:
            startup_result = False
        if not startup_result:
            if hacs.system.disabled_reason != HacsDisabledReason.INVALID_TOKEN:
                hacs.log.info("Could not setup HACS, trying again in 15 min")
                async_call_later(hass, 900, async_try_startup)
            return
        hacs.enable_hacs()

    await async_try_startup()

    # Mischief managed!
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    setup_result = await _async_initialize_integration(
        hass=hass, config_entry=config_entry
    )
    hacs: HacsBase = hass.data[DOMAIN]
    return setup_result and not hacs.system.disabled


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    hacs: HacsBase = hass.data[DOMAIN]

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

    if async_panel_exists(hass, DOMAIN):
        hacs.log.info("Removing sidepanel")
        async_remove_panel(hass, DOMAIN)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hacs.set_stage(None)
    hacs.disable_hacs(HacsDisabledReason.REMOVED)

    hass.data.pop(DOMAIN, None)
    hass.data.pop(STORE_CACHE_KEY, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the HACS config entry."""
    if not await async_unload_entry(hass, config_entry):
        return
    await async_setup_entry(hass, config_entry)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    hacs: HacsBase = hass.data[DOMAIN]
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
            f"Cannot remove service {device_entry.id}, no valid HACS repository identifier found."
        )

    if repository_id == HACS_SYSTEM_ID:
        raise HomeAssistantError("Cannot remove the service for HACS itself.")

    if hacs.repositories.is_downloaded(repository_id):
        repository = hacs.repositories.get_by_id(repository_id)
        raise HomeAssistantError(
            f"Cannot remove service for {repository.data.full_name}, it is still downloaded in HACS."
        )

    return True
