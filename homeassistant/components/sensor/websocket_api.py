"""The sensor websocket API."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DEVICE_CLASS_UNITS


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the sensor websocket API."""
    websocket_api.async_register_command(hass, ws_device_class_units)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "sensor/device_class_units",
        vol.Required("device_class"): str,
    }
)
def ws_device_class_units(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return supported units for a device class."""
    connection.send_result(
        msg["id"], {"units": DEVICE_CLASS_UNITS.get(msg["device_class"], [])}
    )
