"""The weather websocket API."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import VALID_UNITS


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the weather websocket API."""
    websocket_api.async_register_command(hass, ws_convertible_units)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "weather/convertible_units",
    }
)
def ws_convertible_units(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return supported units for a device class."""
    sorted_units = {
        key: sorted(units, key=str.casefold) for key, units in VALID_UNITS.items()
    }
    connection.send_result(msg["id"], {"units": sorted_units})
