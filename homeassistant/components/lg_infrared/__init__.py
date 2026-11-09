"""LG IR Remote integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.EVENT,
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up LG IR from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a LG IR config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old config entry."""
    if entry.version == 1:
        # v1 used the infrared entity_id in the entry's unique_id, which is
        # not stable and was removed in v2.
        _LOGGER.debug("Migrating config entry from version 1 to 2")
        hass.config_entries.async_update_entry(entry, unique_id=None, version=2)
