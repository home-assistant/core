"""Mobile app utility functions."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.components import cloud
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_APP_DATA,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_PUSH_WEBSOCKET_CHANNEL,
    CONF_CLOUDHOOK_URL,
    DATA_CONFIG_ENTRIES,
    DATA_DEVICES,
    DATA_NOTIFY,
    DOMAIN,
)

if TYPE_CHECKING:
    from .notify import MobileAppNotificationService


@callback
def webhook_id_from_device_id(hass: HomeAssistant, device_id: str) -> str | None:
    """Get webhook ID from device ID."""
    if DOMAIN not in hass.data:
        return None

    for cur_webhook_id, cur_device in hass.data[DOMAIN][DATA_DEVICES].items():
        if cur_device.id == device_id:
            return cur_webhook_id

    return None


@callback
def supports_push(hass: HomeAssistant, webhook_id: str) -> bool:
    """Return if push notifications is supported."""
    config_entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]
    app_data = config_entry.data[ATTR_APP_DATA]
    return (
        ATTR_PUSH_TOKEN in app_data and ATTR_PUSH_URL in app_data
    ) or ATTR_PUSH_WEBSOCKET_CHANNEL in app_data


@callback
def get_notify_service(hass: HomeAssistant, webhook_id: str) -> str | None:
    """Return the notify service for this webhook ID."""
    notify_service: MobileAppNotificationService = hass.data[DOMAIN][DATA_NOTIFY]

    for target_service, target_webhook_id in notify_service.registered_targets.items():
        if target_webhook_id == webhook_id:
            return target_service

    return None


_CLOUD_HOOK_LOCK = asyncio.Lock()


async def async_create_cloud_hook(
    hass: HomeAssistant, webhook_id: str, entry: ConfigEntry | None
) -> str:
    """Create a cloud hook."""
    async with _CLOUD_HOOK_LOCK:
        hook = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
        if entry:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_CLOUDHOOK_URL: hook}
            )
        return hook
