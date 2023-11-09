"""The sensor websocket API."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    DEVICE_CLASS_UNITS,
    NON_NUMERIC_DEVICE_CLASSES,
    UNIT_CONVERTERS,
    SensorDeviceClass,
)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the sensor websocket API."""
    websocket_api.async_register_command(hass, ws_device_class_units)
    websocket_api.async_register_command(hass, ws_numeric_device_classes)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "sensor/device_class_convertible_units",
        vol.Required("device_class"): str,
    }
)
def ws_device_class_units(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return supported units for a device class."""
    device_class = msg["device_class"]
    convertible_units = []
    if device_class in UNIT_CONVERTERS and device_class in DEVICE_CLASS_UNITS:
        convertible_units = sorted(
            DEVICE_CLASS_UNITS[device_class],
            key=lambda s: str.casefold(str(s)),
        )
    connection.send_result(msg["id"], {"units": convertible_units})


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "sensor/numeric_device_classes",
    }
)
def ws_numeric_device_classes(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return numeric sensor device classes."""
    numeric_device_classes = set(SensorDeviceClass) - NON_NUMERIC_DEVICE_CLASSES
    connection.send_result(
        msg["id"], {"numeric_device_classes": list(numeric_device_classes)}
    )
