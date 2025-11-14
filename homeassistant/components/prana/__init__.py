"""Home Assistant Prana integration entry point.

Sets up the update coordinator and forwards platform setups.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_CONFIG, DOMAIN
from .coordinator import PranaCoordinator

_LOGGER = logging.getLogger(__name__)

# Keep platforms sorted alphabetically to satisfy lint rule
PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Prana from a config entry.

    Creates and refreshes the coordinator, stores it in runtime_data and forwards
    platform setups.
    """
    try:
        coordinator = PranaCoordinator(hass, entry, entry.data.get(CONF_CONFIG))
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Device not ready: {err}") from err

    # Bronze runtime-data rule: store non-persistent objects here
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Prana integration platforms and coordinator."""
    _LOGGER.info("Unloading Prana integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
