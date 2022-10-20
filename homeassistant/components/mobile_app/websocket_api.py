"""Mobile app websocket API."""
from __future__ import annotations

from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONF_USER_ID, DATA_CONFIG_ENTRIES, DATA_PUSH_CHANNEL, DOMAIN
from .push_notification import PushChannel


@callback
def async_setup_commands(hass):
    """Set up the mobile app websocket API."""
    websocket_api.async_register_command(hass, handle_push_notification_channel)
    websocket_api.async_register_command(hass, handle_push_notification_confirm)


def _ensure_webhook_access(func):
    """Decorate WS function to ensure user owns the webhook ID."""

    @callback
    @wraps(func)
    def with_webhook_access(hass, connection, msg):
        # Validate that the webhook ID is registered to the user of the websocket connection
        config_entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES].get(msg["webhook_id"])

        if config_entry is None:
            connection.send_error(
                msg["id"], websocket_api.ERR_NOT_FOUND, "Webhook ID not found"
            )
            return

        if config_entry.data[CONF_USER_ID] != connection.user.id:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_UNAUTHORIZED,
                "User not linked to this webhook ID",
            )
            return

        func(hass, connection, msg)

    return with_webhook_access


@callback
@_ensure_webhook_access
@websocket_api.websocket_command(
    {
        vol.Required("type"): "mobile_app/push_notification_confirm",
        vol.Required("webhook_id"): str,
        vol.Required("confirm_id"): str,
    }
)
def handle_push_notification_confirm(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Confirm receipt of a push notification."""
    channel: PushChannel | None = hass.data[DOMAIN][DATA_PUSH_CHANNEL].get(
        msg["webhook_id"]
    )
    if channel is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Push notification channel not found",
        )
        return

    if channel.async_confirm_notification(msg["confirm_id"]):
        connection.send_result(msg["id"])
    else:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Push notification channel not found",
        )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "mobile_app/push_notification_channel",
        vol.Required("webhook_id"): str,
        vol.Optional("support_confirm", default=False): bool,
    }
)
@_ensure_webhook_access
@websocket_api.async_response
async def handle_push_notification_channel(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set up a direct push notification channel."""
    webhook_id = msg["webhook_id"]
    registered_channels: dict[str, PushChannel] = hass.data[DOMAIN][DATA_PUSH_CHANNEL]

    if webhook_id in registered_channels:
        await registered_channels[webhook_id].async_teardown()

    @callback
    def on_channel_teardown():
        """Handle teardown."""
        if registered_channels.get(webhook_id) == channel:
            registered_channels.pop(webhook_id)

        # Remove subscription from connection if still exists
        connection.subscriptions.pop(msg["id"], None)

    channel = registered_channels[webhook_id] = PushChannel(
        hass,
        webhook_id,
        msg["support_confirm"],
        lambda data: connection.send_message(
            websocket_api.messages.event_message(msg["id"], data)
        ),
        on_channel_teardown,
    )

    connection.subscriptions[msg["id"]] = lambda: hass.async_create_task(
        channel.async_teardown()
    )
    connection.send_result(msg["id"])
