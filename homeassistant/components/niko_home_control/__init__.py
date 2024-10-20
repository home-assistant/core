"""The Niko home control integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import Hub

PLATFORMS: list[str] = ["light", "cover", "fan"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set Niko Home Control from a config entry."""
    config = entry.data["config"]
    options = entry.data["options"]
    enabled_entities = entry.data["entities"]
    hub = Hub(hass, config["name"], config["host"], config["port"], entry.entry_id)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "enabled_entities": enabled_entities,
        "options": options,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hub.start_events()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
