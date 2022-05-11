"""The Hardware websocket API."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

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
    boards = []

    hardware_platform: dict[str, HardwareProtocol] = hass.data[DOMAIN][
        "hardware_platform"
    ]
    for platform in hardware_platform.values():
        if hasattr(platform, "async_board_info"):
            boards.append(platform.async_board_info())

    hardware_info = {
        "boards": boards,
    }
    connection.send_result(msg["id"], hardware_info)
