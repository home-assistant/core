"""The Telegram client integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CLIENT_PARAMS,
    DOMAIN,
    EVENT_CALLBACK_QUERY,
    EVENT_CHAT_ACTION,
    EVENT_INLINE_QUERY,
    EVENT_MESSAGE_DELETED,
    EVENT_MESSAGE_EDITED,
    EVENT_MESSAGE_READ,
    EVENT_NEW_MESSAGE,
    EVENT_USER_UPDATE,
    KEY_CONFIG_ENTRY_ID,
    OPTION_EVENTS,
    OPTION_INCOMING,
    OPTION_OUTGOING,
    SERVICE_DELETE_MESSAGES,
    SERVICE_EDIT_MESSAGE,
    SERVICE_SEND_MESSAGES,
)
from .coordinator import TelegramClientCoordinator, TelegramClientEntryConfigEntry
from .schemas import (
    SERVICE_DELETE_MESSAGES_SCHEMA,
    SERVICE_EDIT_MESSAGE_SCHEMA,
    SERVICE_SEND_MESSAGES_SCHEMA,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Handle Telegram client integration setup."""
    _register_service(hass, SERVICE_SEND_MESSAGES, SERVICE_SEND_MESSAGES_SCHEMA)
    _register_service(hass, SERVICE_EDIT_MESSAGE, SERVICE_EDIT_MESSAGE_SCHEMA)
    _register_service(hass, SERVICE_DELETE_MESSAGES, SERVICE_DELETE_MESSAGES_SCHEMA)
    CLIENT_PARAMS["lang_code"] = CLIENT_PARAMS["system_lang_code"] = (
        hass.config.language
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
) -> bool:
    """Handle Telegram client config entry setup."""

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                OPTION_EVENTS: {
                    EVENT_NEW_MESSAGE: True,
                    EVENT_MESSAGE_EDITED: True,
                    EVENT_MESSAGE_READ: True,
                    EVENT_MESSAGE_DELETED: True,
                    EVENT_CALLBACK_QUERY: True,
                    EVENT_INLINE_QUERY: True,
                    EVENT_CHAT_ACTION: True,
                    EVENT_USER_UPDATE: True,
                },
                EVENT_NEW_MESSAGE: {
                    OPTION_INCOMING: True,
                    OPTION_OUTGOING: True,
                },
                EVENT_MESSAGE_EDITED: {
                    OPTION_INCOMING: True,
                    OPTION_OUTGOING: True,
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
    """Handle Telegram client config entry unload."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: TelegramClientCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_client_disconnect()

    return True


def _register_service(hass: HomeAssistant, service: str, schema):
    async def async_service_handler(call: ServiceCall):
        data = dict(call.data)
        coordinator = hass.data[DOMAIN].get(
            data.pop(KEY_CONFIG_ENTRY_ID, list(hass.data[DOMAIN].keys())[0])
        )
        handler = getattr(coordinator, call.service)
        return await handler(data)

    return hass.services.async_register(DOMAIN, service, async_service_handler, schema)
