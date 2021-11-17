"""The Onkyo component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_RECEIVER, DOMAIN
from .receiver import OnkyoNetworkReceiver

PLATFORMS: list[str] = ["media_player"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Onkyo/Pioneer Network Receiver from a config entry."""
    receiver = await OnkyoNetworkReceiver.async_from_config_entry(hass, entry)

    if not receiver.online and not await receiver.async_connect():
        raise ConfigEntryNotReady(f"Failed to connect to {receiver.name}")

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CONF_RECEIVER: receiver,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    await hass.data[DOMAIN][entry.entry_id][CONF_RECEIVER].async_disconnect()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
