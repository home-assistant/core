"""The Onkyo component."""
from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import CONF_RECEIVER, DOMAIN
from .receiver import OnkyoNetworkReceiver

PLATFORMS: list[str] = ["media_player"]
UNDO_UPDATE_LISTENER: str = "undo_update_listener"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Onkyo component."""
    # Initiate the onkyo name space as a dict.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Onkyo/Pioneer Network Receiver from a config entry."""
    receiver = await OnkyoNetworkReceiver.async_from_config_entry(hass, entry)

    if not receiver.online and not await receiver.async_connect():
        raise ConfigEntryNotReady(f"Failed to connect to {receiver.name}")

    undo_listener = entry.add_update_listener(update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_RECEIVER: receiver,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data[UNDO_UPDATE_LISTENER]()
    entry_data[CONF_RECEIVER].disconnect()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
