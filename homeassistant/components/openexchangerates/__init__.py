"""The Open Exchange Rates integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_BASE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_UPDATE_INTERVAL, DOMAIN, LOGGER
from .coordinator import OpenexchangeratesConfigEntry, OpenexchangeratesCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenexchangeratesConfigEntry
) -> bool:
    """Set up Open Exchange Rates from a config entry."""
    api_key: str = entry.data[CONF_API_KEY]
    base: str = entry.data[CONF_BASE]

    # Create one coordinator per base currency per API key.
    existing_coordinator_for_api_key = {
        existing_entry.runtime_data
        for existing_entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if existing_entry.data[CONF_API_KEY] == api_key
    }

    # Adjust update interval by coordinators per API key.
    update_interval = BASE_UPDATE_INTERVAL * (len(existing_coordinator_for_api_key) + 1)
    coordinator = OpenexchangeratesCoordinator(
        hass,
        entry,
        async_get_clientsession(hass),
        api_key,
        base,
        update_interval,
    )

    LOGGER.debug("Coordinator update interval set to: %s", update_interval)

    # Set new interval on all coordinators for this API key.
    for existing_coordinator in existing_coordinator_for_api_key:
        existing_coordinator.update_interval = update_interval

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenexchangeratesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
