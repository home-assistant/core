"""The imap integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from aioimaplib import IMAP4_SSL, AioImapException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ImapDataUpdateCoordinator, connect_to_server

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up imap from a config entry."""
    try:
        imap_client: IMAP4_SSL = await connect_to_server(dict(entry.data))
    except AioImapException as err:
        raise ConfigEntryAuthFailed from err
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady from err

    coordinator = ImapDataUpdateCoordinator(hass, imap_client)
    await coordinator.async_config_entry_first_refresh()

    if coordinator.support_push:
        coordinator.idle_loop_task = asyncio.create_task(coordinator.idle_loop())
    else:
        coordinator.update_interval = timedelta(seconds=10)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: ImapDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.shutdown()
    return unload_ok
