"""The AWS Data integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER, DOMAIN, USER_INPUT_DATA, USER_INPUT_REGIONS

# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AWS Data from a config entry."""

    _LOGGER.warning(
        "Setup: %s", entry.data[DOMAIN][USER_INPUT_DATA][USER_INPUT_REGIONS]
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
