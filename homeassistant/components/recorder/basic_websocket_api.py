"""The Recorder websocket API."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import recorder as recorder_helper

from . import format_default_url
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
@websocket_api.async_response
async def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return status of the recorder."""
    # Wait for db_connected to ensure the recorder instance is created and the
    # migration flags are set.
    await hass.data[recorder_helper.DATA_RECORDER].db_connected
    instance = get_instance(hass)
    backlog = instance.backlog
    default_db_url = instance.db_url == format_default_url(hass)
    migration_in_progress = instance.migration_in_progress
    migration_is_live = instance.migration_is_live
    recording = instance.recording
    # We avoid calling is_alive() as it can block waiting
    # for the thread state lock which will block the event loop.
    is_running = instance.is_running
    max_backlog = instance.max_backlog

    recorder_info = {
        "backlog": backlog,
        "default_db_url": default_db_url,
        "max_backlog": max_backlog,
        "migration_in_progress": migration_in_progress,
        "migration_is_live": migration_is_live,
        "recording": recording,
        "thread_running": is_running,
    }
    connection.send_result(msg["id"], recorder_info)
