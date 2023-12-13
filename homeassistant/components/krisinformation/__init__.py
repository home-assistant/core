"""The init-file for the Krisinformation integration."""
from __future__ import annotations

# Importing necessary modules and classes.
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

# Importing custom constants and logger from the integration.
from .const import DOMAIN
from .geo_location import _LOGGER

# List of the platforms that the integration supports.
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.GEO_LOCATION]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Asynchronous function to set up the krisinformation integration when a configuration entry is added."""

    hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("Feed entity manager added for %s", entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Asynchronous function to unload the integration when a configuration entry is removed."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
