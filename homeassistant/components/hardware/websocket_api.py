"""The Hardware websocket API."""

from __future__ import annotations

import contextlib
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DATA_HARDWARE


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the hardware websocket API."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_subscribe_system_status)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hardware/info",
    }
)
@websocket_api.async_response
async def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return hardware info."""
    hardware_info = []

    hardware_platform = hass.data[DATA_HARDWARE].hardware_platform
    for platform in hardware_platform.values():
        if hasattr(platform, "async_info"):
            with contextlib.suppress(HomeAssistantError):
                hardware_info.extend([asdict(hw) for hw in platform.async_info(hass)])

    connection.send_result(msg["id"], {"hardware": hardware_info})


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "hardware/subscribe_system_status",
    }
)
def ws_subscribe_system_status(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to system status updates."""

    system_status = hass.data[DATA_HARDWARE].system_status

    @callback
    def async_update_status(now: datetime) -> None:
        # Although cpu_percent and virtual_memory access files in the /proc vfs, those
        # accesses do not block and we don't need to wrap the calls in an executor.
        # https://elixir.bootlin.com/linux/v5.19.4/source/fs/proc/stat.c
        # https://elixir.bootlin.com/linux/v5.19.4/source/fs/proc/meminfo.c#L32
        cpu_percentage = round(
            system_status.ha_psutil.psutil.cpu_percent(interval=None)
        )
        virtual_memory = system_status.ha_psutil.psutil.virtual_memory()
        json_msg = {
            "cpu_percent": cpu_percentage,
            "memory_used_percent": virtual_memory.percent,
            "memory_used_mb": round(
                (virtual_memory.total - virtual_memory.available) / 1024**2, 1
            ),
            "memory_free_mb": round(virtual_memory.available / 1024**2, 1),
            "timestamp": dt_util.utcnow().isoformat(),
        }
        for conn, msg_id in system_status.subscribers:
            conn.send_message(websocket_api.event_message(msg_id, json_msg))

    if not system_status.subscribers:
        system_status.remove_periodic_timer = async_track_time_interval(
            hass, async_update_status, timedelta(seconds=5)
        )

    system_status.subscribers.add((connection, msg["id"]))

    @callback
    def cancel_subscription() -> None:
        system_status.subscribers.remove((connection, msg["id"]))
        if not system_status.subscribers and system_status.remove_periodic_timer:
            system_status.remove_periodic_timer()
            system_status.remove_periodic_timer = None

    connection.subscriptions[msg["id"]] = cancel_subscription

    connection.send_message(websocket_api.result_message(msg["id"]))
