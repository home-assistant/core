"""The Roth Touchline SL integration."""

from __future__ import annotations

from pytouchlinesl import TouchlineSL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type TouchlineSLConfigEntry = ConfigEntry[TouchlineSL]


async def async_setup_entry(hass: HomeAssistant, entry: TouchlineSLConfigEntry) -> bool:
    """Set up Roth Touchline SL from a config entry."""
    account = TouchlineSL(
        username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
    )
    entry.runtime_data = account

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TouchlineSLConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
