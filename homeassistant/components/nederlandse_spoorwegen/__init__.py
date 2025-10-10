"""The Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging

from ns_api import RequestParametersError
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


type NSConfigEntry = ConfigEntry[NSDataUpdateCoordinator]

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""

    coordinator = NSDataUpdateCoordinator(hass, entry)

    # Test the API connection before proceeding
    try:
        await coordinator.get_stations()
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.HTTPError,
    ) as error:
        _LOGGER.error("Could not connect to the internet: %s", error)
        raise ConfigEntryNotReady from error
    except RequestParametersError as error:
        _LOGGER.error("Could not fetch stations, please check configuration: %s", error)
        raise ConfigEntryNotReady from error

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
