"""The System Monitor integration."""

import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up System Monitor from a config entry."""

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload System Monitor config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version == 1:
        new_options = {**entry.options}
        if entry.minor_version == 1:
            # Migration copies process sensors to binary sensors
            # Repair will remove sensors when user submit the fix
            if processes := entry.options.get(SENSOR_DOMAIN):
                new_options[BINARY_SENSOR_DOMAIN] = processes
        entry.version = 1
        entry.minor_version = 2
        hass.config_entries.async_update_entry(entry, options=new_options)

    _LOGGER.debug(
        "Migration to version %s.%s successful", entry.version, entry.minor_version
    )

    return True
