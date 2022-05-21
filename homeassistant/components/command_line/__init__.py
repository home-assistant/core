"""The command_line component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up command line from a config entry."""

    platform = [entry.options[CONF_PLATFORM]]

    if platform == [Platform.NOTIFY]:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.options
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                hass.data[DOMAIN][entry.entry_id],
                hass.data[DOMAIN],
            )
        )
        return True

    hass.config_entries.async_setup_platforms(entry, platform)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload command line config entry."""

    platform = [entry.options[CONF_PLATFORM]]
    return await hass.config_entries.async_unload_platforms(entry, platform)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    await hass.config_entries.async_reload(entry.entry_id)
