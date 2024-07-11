"""The Telegram client integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    EVENT_CALLBACK_QUERY,
    EVENT_CHAT_ACTION,
    EVENT_INLINE_QUERY,
    EVENT_MESSAGE_DELETED,
    EVENT_MESSAGE_EDITED,
    EVENT_MESSAGE_READ,
    EVENT_NEW_MESSAGE,
    EVENT_USER_UPDATE,
    OPTION_BLACKLIST_CHATS,
    OPTION_DATA,
    OPTION_EVENTS,
    OPTION_INBOX,
    OPTION_INCOMING,
    OPTION_OUTGOING,
    OPTION_PATTERN,
)
from .coordinator import TelegramClientCoordinator, TelegramClientEntryConfigEntry

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Telegram client component."""

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
) -> bool:
    """Handle Telegram client entry setup."""
    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                OPTION_EVENTS: {
                    EVENT_NEW_MESSAGE: True,
                    EVENT_MESSAGE_EDITED: True,
                },
                EVENT_NEW_MESSAGE: {
                    OPTION_BLACKLIST_CHATS: False,
                    OPTION_INCOMING: True,
                    OPTION_OUTGOING: True,
                    OPTION_PATTERN: "",
                },
                EVENT_MESSAGE_EDITED: {
                    OPTION_BLACKLIST_CHATS: False,
                    OPTION_INCOMING: True,
                    OPTION_OUTGOING: True,
                    OPTION_PATTERN: "",
                },
                EVENT_MESSAGE_READ: {
                    OPTION_BLACKLIST_CHATS: False,
                    OPTION_INBOX: False,
                },
                EVENT_MESSAGE_DELETED: {
                    OPTION_BLACKLIST_CHATS: False,
                },
                EVENT_CALLBACK_QUERY: {
                    OPTION_BLACKLIST_CHATS: False,
                    OPTION_DATA: "",
                    OPTION_PATTERN: "",
                },
                EVENT_INLINE_QUERY: {
                    OPTION_BLACKLIST_CHATS: False,
                    OPTION_PATTERN: "",
                },
                EVENT_CHAT_ACTION: {
                    OPTION_BLACKLIST_CHATS: False,
                },
                EVENT_USER_UPDATE: {
                    OPTION_BLACKLIST_CHATS: False,
                },
            },
        )
    coordinator = TelegramClientCoordinator(hass, entry)
    await coordinator.async_client_start()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(coordinator.resubscribe_listeners))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: TelegramClientCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_client_disconnect()

    return True
