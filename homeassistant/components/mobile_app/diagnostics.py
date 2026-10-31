"""Diagnostics support for Mobile App."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from collections import Counter
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_APP_VERSION,
    ATTR_NO_LEGACY_ENCRYPTION,
    ATTR_OS_NAME,
    ATTR_OS_VERSION,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_PUSH_WEBSOCKET_CHANNEL,
    ATTR_START_LIVE_ACTIVITY_TOKEN,
    ATTR_SUPPORTS_ENCRYPTION,
    CONF_CLOUDHOOK_URL,
    DATA_PUSH_CHANNEL,
    DOMAIN,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.data
    app_data = data[ATTR_APP_DATA]
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    return {
        "app": {
            ATTR_APP_ID: data[ATTR_APP_ID],
            ATTR_APP_NAME: data[ATTR_APP_NAME],
            ATTR_APP_VERSION: data[ATTR_APP_VERSION],
        },
        "device": {
            ATTR_MANUFACTURER: data[ATTR_MANUFACTURER],
            ATTR_MODEL: data[ATTR_MODEL],
            ATTR_OS_NAME: data[ATTR_OS_NAME],
            ATTR_OS_VERSION: data.get(ATTR_OS_VERSION),
        },
        "encryption": {
            ATTR_SUPPORTS_ENCRYPTION: data[ATTR_SUPPORTS_ENCRYPTION],
            ATTR_NO_LEGACY_ENCRYPTION: data.get(ATTR_NO_LEGACY_ENCRYPTION, False),
        },
        "push": {
            "cloud_push": ATTR_PUSH_TOKEN in app_data and ATTR_PUSH_URL in app_data,
            ATTR_PUSH_WEBSOCKET_CHANNEL: app_data.get(
                ATTR_PUSH_WEBSOCKET_CHANNEL, False
            ),
            "websocket_channel_connected": (
                data[CONF_WEBHOOK_ID] in hass.data[DOMAIN][DATA_PUSH_CHANNEL]
            ),
            "live_activity": ATTR_START_LIVE_ACTIVITY_TOKEN in app_data,
        },
        "cloudhook": CONF_CLOUDHOOK_URL in data,
        "entities": dict(Counter(entity.domain for entity in entities)),
    }
