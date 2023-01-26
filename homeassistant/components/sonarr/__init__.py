"""The Sonarr component."""
from __future__ import annotations

from typing import Any

from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.sonarr_client import SonarrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
    LOGGER,
)
from .coordinator import (
    CalendarDataUpdateCoordinator,
    CommandsDataUpdateCoordinator,
    DiskSpaceDataUpdateCoordinator,
    QueueDataUpdateCoordinator,
    SeriesDataUpdateCoordinator,
    SonarrDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
    WantedDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonarr from a config entry."""
    if not entry.options:
        options = {
            CONF_UPCOMING_DAYS: entry.data.get(
                CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
            ),
            CONF_WANTED_MAX_ITEMS: entry.data.get(
                CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
            ),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    host_configuration = PyArrHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        url=entry.data[CONF_URL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    sonarr = SonarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass),
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    coordinators: dict[str, SonarrDataUpdateCoordinator[Any]] = {
        "upcoming": CalendarDataUpdateCoordinator(hass, host_configuration, sonarr),
        "commands": CommandsDataUpdateCoordinator(hass, host_configuration, sonarr),
        "diskspace": DiskSpaceDataUpdateCoordinator(hass, host_configuration, sonarr),
        "queue": QueueDataUpdateCoordinator(hass, host_configuration, sonarr),
        "series": SeriesDataUpdateCoordinator(hass, host_configuration, sonarr),
        "status": StatusDataUpdateCoordinator(hass, host_configuration, sonarr),
        "wanted": WantedDataUpdateCoordinator(hass, host_configuration, sonarr),
    }
    # Temporary, until we add diagnostic entities
    _version = None
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
        if isinstance(coordinator, StatusDataUpdateCoordinator):
            _version = coordinator.data.version
        coordinator.system_version = _version
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        new_proto = "https" if entry.data[CONF_SSL] else "http"
        new_host_port = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"

        new_path = ""

        if entry.data[CONF_BASE_PATH].rstrip("/") not in ("", "/", "/api"):
            new_path = entry.data[CONF_BASE_PATH].rstrip("/")

        data = {
            **entry.data,
            CONF_URL: f"{new_proto}://{new_host_port}{new_path}",
        }
        hass.config_entries.async_update_entry(entry, data=data)
        entry.version = 2

    LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
