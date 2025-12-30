"""Set up the Elke27 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = dict(entry.data)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
