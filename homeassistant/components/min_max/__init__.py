"""The min_max component."""

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Min/Max from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        # Migration to group sensor and remove config entry
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=entry.options
            )
        )
        hass.config_entries.async_update_entry(entry, version=2)

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True
