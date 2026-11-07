"""The dlna_dmr component."""

from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import LOGGER

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Set up a DLNA DMR device from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.unique_id)

    # Forward setup to the appropriate platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> None:
    """Unload a config entry."""
    # Forward to the same platform as async_setup_entry did
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
