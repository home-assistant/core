"""Support for displaying persistent notifications."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from enum import StrEnum
from functools import partial
import logging
from typing import Any, Final, TypedDict

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, singleton
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util
from homeassistant.util.signal_type import SignalType
from homeassistant.util.uuid import random_uuid_hex

DOMAIN = "persistent_notification"

ATTR_CREATED_AT: Final = "created_at"
ATTR_MESSAGE: Final = "message"
ATTR_NOTIFICATION_ID: Final = "notification_id"
ATTR_TITLE: Final = "title"
ATTR_STATUS: Final = "status"


class Notification(TypedDict):
    """Persistent notification."""

    created_at: datetime
    message: str
    notification_id: str
    title: str | None


class UpdateType(StrEnum):
    """Persistent notification update type."""

    CURRENT = "current"
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"


SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED = SignalType[
    UpdateType, dict[str, Notification]
]("persistent_notifications_updated")

SCHEMA_SERVICE_NOTIFICATION = vol.Schema(
    {vol.Required(ATTR_NOTIFICATION_ID): cv.string}
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@callback
def async_register_callback(
    hass: HomeAssistant,
    _callback: Callable[[UpdateType, dict[str, Notification]], None],
) -> CALLBACK_TYPE:
    """Register a callback."""
    return async_dispatcher_connect(
        hass, SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED, _callback
    )


@bind_hass
def create(
    hass: HomeAssistant,
    message: str,
    title: str | None = None,
    notification_id: str | None = None,
) -> None:
    """Generate a notification."""
    hass.add_job(async_create, hass, message, title, notification_id)


@bind_hass
def dismiss(hass: HomeAssistant, notification_id: str) -> None:
    """Remove a notification."""
    hass.add_job(async_dismiss, hass, notification_id)


@callback
@bind_hass
def async_create(
    hass: HomeAssistant,
    message: str,
    title: str | None = None,
    notification_id: str | None = None,
) -> None:
    """Generate a notification."""
    notifications = _async_get_or_create_notifications(hass)
    if notification_id is None:
        notification_id = random_uuid_hex()
    notifications[notification_id] = {
        ATTR_MESSAGE: message,
        ATTR_NOTIFICATION_ID: notification_id,
        ATTR_TITLE: title,
        ATTR_CREATED_AT: dt_util.utcnow(),
    }

    async_dispatcher_send(
        hass,
        SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
        UpdateType.ADDED,
        {notification_id: notifications[notification_id]},
    )


@callback
@singleton.singleton(DOMAIN)
def _async_get_or_create_notifications(hass: HomeAssistant) -> dict[str, Notification]:
    """Get or create notifications data."""
    return {}


@callback
@bind_hass
def async_dismiss(hass: HomeAssistant, notification_id: str) -> None:
    """Remove a notification."""
    notifications = _async_get_or_create_notifications(hass)
    if not (notification := notifications.pop(notification_id, None)):
        return
    async_dispatcher_send(
        hass,
        SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
        UpdateType.REMOVED,
        {notification_id: notification},
    )


@callback
def async_dismiss_all(hass: HomeAssistant) -> None:
    """Remove all notifications."""
    notifications = _async_get_or_create_notifications(hass)
    notifications_copy = notifications.copy()
    notifications.clear()
    async_dispatcher_send(
        hass,
        SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
        UpdateType.REMOVED,
        notifications_copy,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the persistent notification component."""

    @callback
    def create_service(call: ServiceCall) -> None:
        """Handle a create notification service call."""
        async_create(
            hass,
            call.data[ATTR_MESSAGE],
            call.data.get(ATTR_TITLE),
            call.data.get(ATTR_NOTIFICATION_ID),
        )

    @callback
    def dismiss_service(call: ServiceCall) -> None:
        """Handle the dismiss notification service call."""
        async_dismiss(hass, call.data[ATTR_NOTIFICATION_ID])

    @callback
    def dismiss_all_service(call: ServiceCall) -> None:
        """Handle the dismiss all notification service call."""
        async_dismiss_all(hass)

    hass.services.async_register(
        DOMAIN,
        "create",
        create_service,
        vol.Schema(
            {
                vol.Required(ATTR_MESSAGE): vol.Any(cv.dynamic_template, cv.string),
                vol.Optional(ATTR_TITLE): vol.Any(cv.dynamic_template, cv.string),
                vol.Optional(ATTR_NOTIFICATION_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN, "dismiss", dismiss_service, SCHEMA_SERVICE_NOTIFICATION
    )

    hass.services.async_register(DOMAIN, "dismiss_all", dismiss_all_service, None)

    websocket_api.async_register_command(hass, websocket_get_notifications)
    websocket_api.async_register_command(hass, websocket_subscribe_notifications)

    return True


@callback
@websocket_api.websocket_command({vol.Required("type"): "persistent_notification/get"})
def websocket_get_notifications(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Mapping[str, Any],
) -> None:
    """Return a list of persistent_notifications."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"], list(_async_get_or_create_notifications(hass).values())
        )
    )


@callback
def _async_send_notification_update(
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    update_type: UpdateType,
    notifications: dict[str, Notification],
) -> None:
    """Send persistent_notification update."""
    connection.send_message(
        websocket_api.event_message(
            msg_id, {"type": update_type, "notifications": notifications}
        )
    )


@callback
@websocket_api.websocket_command(
    {vol.Required("type"): "persistent_notification/subscribe"}
)
def websocket_subscribe_notifications(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Mapping[str, Any],
) -> None:
    """Return a list of persistent_notifications."""
    notifications = _async_get_or_create_notifications(hass)
    msg_id = msg["id"]
    notify_func = partial(_async_send_notification_update, connection, msg_id)
    connection.subscriptions[msg_id] = async_dispatcher_connect(
        hass, SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED, notify_func
    )
    connection.send_result(msg_id)
    notify_func(UpdateType.CURRENT, notifications)
