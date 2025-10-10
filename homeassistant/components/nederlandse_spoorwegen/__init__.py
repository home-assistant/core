"""The Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging

from requests.exceptions import ConnectionError, HTTPError, Timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


type NSConfigEntry = ConfigEntry[dict[str, NSDataUpdateCoordinator]]

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""
    coordinators: dict[str, NSDataUpdateCoordinator] = {}

    # Set up coordinators for all existing routes
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == "route":
            coordinator = NSDataUpdateCoordinator(
                hass, entry, subentry_id, dict(subentry.data)
            )

            try:
                await coordinator.async_config_entry_first_refresh()
            except (ConnectionError, Timeout, HTTPError, ValueError) as err:
                _LOGGER.error(
                    "Failed to initialize coordinator for route %s: %s",
                    subentry_id,
                    err,
                )
                raise ConfigEntryNotReady(
                    f"Unable to connect to NS API for route {subentry_id}"
                ) from err

            coordinators[subentry_id] = coordinator
            _LOGGER.debug("Added coordinator for route %s", subentry_id)

    entry.runtime_data = coordinators

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
