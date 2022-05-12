"""The Hardware websocket API."""
from __future__ import annotations

import contextlib

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .models import HardwareProtocol


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the hardware websocket API."""
    websocket_api.async_register_command(hass, ws_info)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hardware/info",
    }
)
@callback
def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return hardware info."""
    hardware_info = []

    hardware_platform: dict[str, HardwareProtocol] = hass.data[DOMAIN][
        "hardware_platform"
    ]
    for platform in hardware_platform.values():
        if hasattr(platform, "async_info"):
            with contextlib.suppress(HomeAssistantError):
                hardware_info.append(platform.async_info(hass))

    connection.send_result(msg["id"], hardware_info)
