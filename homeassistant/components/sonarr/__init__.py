"""The Sonarr component."""

from __future__ import annotations

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
    SERVICE_GET_SERIES,
)
from .coordinator import (
    CalendarDataUpdateCoordinator,
    CommandsDataUpdateCoordinator,
    DiskSpaceDataUpdateCoordinator,
    QueueDataUpdateCoordinator,
    SeriesDataUpdateCoordinator,
    SonarrConfigEntry,
    SonarrData,
    SonarrDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
    WantedDataUpdateCoordinator,
)
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SonarrConfigEntry) -> bool:
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
    data = SonarrData(
        upcoming=CalendarDataUpdateCoordinator(hass, entry, host_configuration, sonarr),
        commands=CommandsDataUpdateCoordinator(hass, entry, host_configuration, sonarr),
        diskspace=DiskSpaceDataUpdateCoordinator(
            hass, entry, host_configuration, sonarr
        ),
        queue=QueueDataUpdateCoordinator(hass, entry, host_configuration, sonarr),
        series=SeriesDataUpdateCoordinator(hass, entry, host_configuration, sonarr),
        status=StatusDataUpdateCoordinator(hass, entry, host_configuration, sonarr),
        wanted=WantedDataUpdateCoordinator(hass, entry, host_configuration, sonarr),
    )
    # Temporary, until we add diagnostic entities
    _version = None
    coordinators: list[SonarrDataUpdateCoordinator] = [
        data.upcoming,
        data.commands,
        data.diskspace,
        data.queue,
        data.series,
        data.status,
        data.wanted,
    ]
    for coordinator in coordinators:
        await coordinator.async_config_entry_first_refresh()
        if isinstance(coordinator, StatusDataUpdateCoordinator):
            _version = coordinator.data.version
        coordinator.system_version = _version
    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only register once for the domain)
    if not hass.services.has_service(DOMAIN, SERVICE_GET_SERIES):
        async_setup_services(hass)

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
        hass.config_entries.async_update_entry(entry, data=data, version=2)

    LOGGER.debug("Migration to version %s successful", entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SonarrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
