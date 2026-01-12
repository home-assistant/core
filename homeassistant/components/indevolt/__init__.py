"""Home Assistant integration for indevolt device."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import IndevoltCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type IndevoltConfigEntry = ConfigEntry[IndevoltCoordinator]

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Set up indevolt integration entry using given configuration."""
    try:
        # Setup coordinator and perform initial data refresh
        coordinator = IndevoltCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()

        # Store coordinator in runtime_data
        entry.runtime_data = coordinator

        # Setup platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    except Exception as err:
        _LOGGER.exception("Unexpected error occurred during initial setup")
        raise ConfigEntryNotReady from err

    else:
        return True


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry and clean up resources (when integration is removed / reloaded)."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.async_shutdown()

    return unload_ok
