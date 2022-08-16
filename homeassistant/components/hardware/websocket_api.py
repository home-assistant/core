"""The Hardware websocket API."""
from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import importlib
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .hardware import async_process_hardware_platforms
from .models import HardwareProtocol

if TYPE_CHECKING:
    import psutil  # noqa: F401


@dataclass
class SystemStatus:
    """System status."""

    psutil: psutil
    remove_periodic_timer: CALLBACK_TYPE | None
    subscribers: set[tuple[websocket_api.ActiveConnection, int]]


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the hardware websocket API."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_subscribe_system_status)
    # Make a local copy of the psutil module because it relies on global variables
    psutil_spec = importlib.util.find_spec("psutil")
    assert psutil_spec and psutil_spec.loader
    psutil_module = importlib.util.module_from_spec(psutil_spec)
    psutil_spec.loader.exec_module(psutil_module)
    hass.data[DOMAIN]["system_status"] = SystemStatus(
        psutil=psutil_module,
        remove_periodic_timer=None,
        subscribers=set(),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hardware/info",
    }
)
@websocket_api.async_response
async def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return hardware info."""
    hardware_info = []

    if "hardware_platform" not in hass.data[DOMAIN]:
        await async_process_hardware_platforms(hass)

    hardware_platform: dict[str, HardwareProtocol] = hass.data[DOMAIN][
        "hardware_platform"
    ]
    for platform in hardware_platform.values():
        if hasattr(platform, "async_info"):
            with contextlib.suppress(HomeAssistantError):
                hardware_info.append(asdict(platform.async_info(hass)))

    connection.send_result(msg["id"], {"hardware": hardware_info})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hardware/subscribe_system_status",
    }
)
@websocket_api.async_response
async def ws_subscribe_system_status(hass, connection, msg):
    """Subscribe to system status updates."""

    system_status: SystemStatus = hass.data[DOMAIN]["system_status"]

    @callback
    def async_update_status(now: datetime) -> None:
        cpu_percentage = round(system_status.psutil.cpu_percent(interval=None))
        virtual_memory = system_status.psutil.virtual_memory()
        json_msg = {
            "cpu_percentage": cpu_percentage,
            "memory_use_percent": virtual_memory.percent,
            "memory_use": round(
                (virtual_memory.total - virtual_memory.available) / 1024**2, 1
            ),
            "memory_free": round(virtual_memory.available / 1024**2, 1),
        }
        for connection, msg_id in system_status.subscribers:
            connection.send_message(websocket_api.event_message(msg_id, json_msg))

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
