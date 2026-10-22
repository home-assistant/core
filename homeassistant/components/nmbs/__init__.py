"""The NMBS component."""

from pyrail import IRail, PyRailError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import NMBSConfigEntry, NMBSCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
    """Set up NMBS from a config entry."""
    api_client = IRail(session=async_get_clientsession(hass))
    try:
        station_response = await api_client.get_stations()
    except (PyRailError, TimeoutError, ValueError, LookupError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="station_list_unavailable",
        ) from err
    if station_response is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="station_list_unavailable",
        )

    coordinator = NMBSCoordinator(hass, entry, station_response.stations)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
