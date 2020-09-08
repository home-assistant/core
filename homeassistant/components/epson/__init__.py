"""The epson integration."""
import asyncio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_PLATFROM
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DATA_EPSON, DOMAIN, SIGNAL_CONFIG_OPTIONS_UPDATE, UPDATE_LISTENER

PLATFORMS = [MEDIA_PLAYER_PLATFROM]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the epson component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up epson from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_EPSON: [],
        UPDATE_LISTENER: entry.add_update_listener(update_listener),
    }
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        listener = hass.data[DOMAIN][entry.entry_id][UPDATE_LISTENER]
        listener()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass, entry):
    """Handle options update."""
    async_dispatcher_send(
        hass, f"{SIGNAL_CONFIG_OPTIONS_UPDATE} {entry.entry_id}", entry.options
    )
