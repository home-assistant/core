"""The imap integration."""
from __future__ import annotations

import asyncio

from aioimaplib import IMAP4_SSL, AioImapException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import CONF_ENABLE_PUSH, DOMAIN
from .coordinator import (
    ImapPollingDataUpdateCoordinator,
    ImapPushDataUpdateCoordinator,
    connect_to_server,
)
from .errors import InvalidAuth, InvalidFolder

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up imap from a config entry."""
    try:
        imap_client: IMAP4_SSL = await connect_to_server(dict(entry.data))
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed from err
    except InvalidFolder as err:
        raise ConfigEntryError("Selected mailbox folder is invalid.") from err
    except (asyncio.TimeoutError, AioImapException) as err:
        raise ConfigEntryNotReady from err

    coordinator_class: type[
        ImapPushDataUpdateCoordinator | ImapPollingDataUpdateCoordinator
    ]
    enable_push: bool = entry.data.get(CONF_ENABLE_PUSH, True)
    if enable_push and imap_client.has_capability("IDLE"):
        coordinator_class = ImapPushDataUpdateCoordinator
    else:
        coordinator_class = ImapPollingDataUpdateCoordinator

    coordinator: ImapPushDataUpdateCoordinator | ImapPollingDataUpdateCoordinator = (
        coordinator_class(hass, imap_client, entry)
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: ImapPushDataUpdateCoordinator | ImapPollingDataUpdateCoordinator = hass.data[
            DOMAIN
        ].pop(
            entry.entry_id
        )
        await coordinator.shutdown()
    return unload_ok
