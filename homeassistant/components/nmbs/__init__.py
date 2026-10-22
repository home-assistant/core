"""The NMBS component."""

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    NMBSConfigEntry,
    NMBSCoordinator,
    StationListUnavailableError,
    async_fetch_stations,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
    """Set up NMBS from a config entry."""
    try:
        stations = await async_fetch_stations(hass)
    except StationListUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="station_list_unavailable",
        ) from err

    coordinator = NMBSCoordinator(hass, entry, stations)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
