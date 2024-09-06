"""The Recorder websocket API."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .util import get_instance


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder websocket API."""
    websocket_api.async_register_command(hass, ws_info)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/info",
    }
)
@callback
def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return status of the recorder."""
    if instance := get_instance(hass):
        backlog = instance.backlog
        migration_in_progress = instance.migration_in_progress
        migration_is_live = instance.migration_is_live
        recording = instance.recording
        # We avoid calling is_alive() as it can block waiting
        # for the thread state lock which will block the event loop.
        is_running = instance.is_running
        max_backlog = instance.max_backlog
    else:
        backlog = None
        migration_in_progress = False
        migration_is_live = False
        recording = False
        is_running = False
        max_backlog = None

    recorder_info = {
        "backlog": backlog,
        "max_backlog": max_backlog,
        "migration_in_progress": migration_in_progress,
        "migration_is_live": migration_is_live,
        "recording": recording,
        "thread_running": is_running,
    }
    connection.send_result(msg["id"], recorder_info)
