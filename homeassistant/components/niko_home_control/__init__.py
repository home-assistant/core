"""The Niko home control integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[str] = ["light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set Niko Home Control from a config entry."""
    config = entry.data["config"]
    options = entry.data["options"]
    enabled_entities = entry.data["entities"]

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "config": config,
        "enabled_entities": enabled_entities,
        "options": options,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
