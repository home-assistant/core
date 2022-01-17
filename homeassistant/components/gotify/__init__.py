"""The gotify integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up gotify from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry
    # Gotify notify component requires entry_id in discovery_info to get the correct entry config.
    # The discovery platform requires CONF_NAME in discovery_info to set a service name.
    discovery_info = {CONF_NAME: entry.data[CONF_NAME], "entry_id": entry.entry_id}
    await hass.async_create_task(
        discovery.async_load_platform(
            hass, "notify", DOMAIN, discovery_info, hass.data[DOMAIN]
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.services.async_remove("notify", entry.data[CONF_NAME])
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
