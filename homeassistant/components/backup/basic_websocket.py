"""Websocket commands for the Backup integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.backup import async_subscribe_events

from .const import DATA_MANAGER
from .manager import ManagerStateEvent


@callback
def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, handle_subscribe_events)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/subscribe_events"})
@websocket_api.async_response
async def handle_subscribe_events(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to backup events."""

    def on_event(event: ManagerStateEvent) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], event))

    if DATA_MANAGER in hass.data:
        manager = hass.data[DATA_MANAGER]
        on_event(manager.last_event)
    connection.subscriptions[msg["id"]] = async_subscribe_events(hass, on_event)
    connection.send_result(msg["id"])
