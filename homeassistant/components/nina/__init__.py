"""The Nina integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[str] = ["binary_sensor"]  # pylint: disable=E1136


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True
