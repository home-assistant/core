"""Diagnostics support for Motionblinds Bluetooth."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import MotionConfigEntry

CONF_TITLE = "title"

TO_REDACT: Iterable[Any] = {
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MotionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "device": {
                "blind_type": device.blind_type.value,
                "timezone": device.timezone,
                "position": device._position,  # noqa: SLF001
                "tilt": device._tilt,  # noqa: SLF001
                "calibration_type": device._calibration_type.value  # noqa: SLF001
                if device._calibration_type  # noqa: SLF001
                else None,
                "connection_type": device._connection_type.value,  # noqa: SLF001
                "end_position_info": None
                if not device._end_position_info  # noqa: SLF001
                else {
                    "end_positions": device._end_position_info.end_positions.value,  # noqa: SLF001
                    "favorite": device._end_position_info.favorite_position,  # noqa: SLF001
                },
            },
        },
        TO_REDACT,
    )
