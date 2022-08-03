"""The pjlink component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import _LOGGER, DOMAIN


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        config_entry.version = 2
        unique_id = f"{DOMAIN}-{config_entry.entry_id}"
        hass.config_entries.async_update_entry(config_entry, unique_id=unique_id)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
