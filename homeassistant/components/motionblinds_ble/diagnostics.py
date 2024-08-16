"""Diagnostics support for Motionblinds Bluetooth."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from motionblindsble.device import MotionDevice

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .const import DOMAIN

CONF_TITLE = "title"

TO_REDACT: Iterable[Any] = {
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device: MotionDevice = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "device": {
                "blind_type": device.blind_type.value,
                "display_name": device.display_name,
                "timezone": device.timezone,
                "states": {
                    "_end_position_info": None
                    if not device._end_position_info  # noqa: SLF001
                    else {
                        "end_positions": device._end_position_info.end_positions.value,  # noqa: SLF001
                        "favorite": device._end_position_info.favorite_position,  # noqa: SLF001
                    },
                    **{
                        attr: getattr(device, attr)
                        for attr in (
                            "_position",
                            "_tilt",
                            "_calibration_type",
                        )
                    },
                },
                "connection": {
                    "has_ble_device": device.ble_device is not None,  # noqa: SLF001
                    "has_bleak_client": device._current_bleak_client is not None,  # noqa: SLF001
                    "has_disconnect_timer": device._disconnect_timer is not None,  # noqa: SLF001
                    "is_set_received_end_position_info_event": device._received_end_position_info_event.is_set(),  # noqa: SLF001
                    "_connection_type": device._connection_type.value,  # noqa: SLF001
                    **{
                        attr: getattr(device, attr)
                        for attr in (
                            "rssi",
                            "_permanent_connection",
                            "_connect_status_query_time",
                            "_custom_setting_disconnect_time",
                            "_disconnect_time",
                        )
                    },
                },
                "callbacks": {
                    callback: [
                        f"{method.__self__.__class__.__name__}.{method.__name__}"
                        if hasattr(method, "__self__")
                        else method.__name__
                        for method in getattr(device, callback)
                    ]
                    for callback in (
                        "_battery_callbacks",
                        "_calibration_callbacks",
                        "_connection_callbacks",
                        "_disabled_connection_callbacks",
                        "_end_position_callbacks",
                        "_feedback_callbacks",
                        "_position_callbacks",
                        "_running_callbacks",
                        "_signal_strength_callbacks",
                        "_speed_callbacks",
                        "_status_callbacks",
                    )
                },
            },
        },
        TO_REDACT,
    )
