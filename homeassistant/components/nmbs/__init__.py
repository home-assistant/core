"""The NMBS component."""

import logging

from homeassistant.const import CONF_SHOW_ON_MAP
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

_LOGGER = logging.getLogger(__name__)

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


async def async_migrate_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
    """Migrate an old config entry."""
    if entry.minor_version < 2:
        data = dict(entry.data)
        show_on_map = data.pop(CONF_SHOW_ON_MAP, False)
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options={**entry.options, CONF_SHOW_ON_MAP: show_on_map},
            minor_version=2,
        )
        _LOGGER.debug("Moved the map setting of %s to the options", entry.title)
