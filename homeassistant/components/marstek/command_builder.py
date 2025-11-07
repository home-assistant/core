"""Command builder for Marstek devices.

Build the JSON string of the request command.
"""

from __future__ import annotations

import json
from typing import Any

from .const import (
    CMD_BATTERY_STATUS,
    CMD_DISCOVER,
    CMD_ES_MODE,
    CMD_ES_SET_MODE,
    CMD_ES_STATUS,
    CMD_PV_GET_STATUS,
)

# Request ID counter
_request_id = 0


def get_next_request_id() -> int:
    """Get next request ID."""
    global _request_id  # noqa: PLW0603 - global state needed for request ID counter
    _request_id += 1
    return _request_id


def reset_request_id() -> None:
    """Reset request ID counter."""
    global _request_id  # noqa: PLW0603 - global state needed for request ID counter
    _request_id = 0


def build_command(method: str, params: dict[str, Any] | None = None) -> str:
    """Build command JSON string."""
    command = {
        "id": get_next_request_id(),
        "method": method,
        "params": params or {},
    }
    return json.dumps(command)


def discover() -> str:
    """Device discovery command."""
    return build_command(CMD_DISCOVER, {"ble_mac": "0"})


def get_battery_status(device_id: int = 0) -> str:
    """Battery status query command."""
    return build_command(CMD_BATTERY_STATUS, {"id": device_id})


def get_es_status(device_id: int = 0) -> str:
    """Get device power status and statistics command."""
    return build_command(CMD_ES_STATUS, {"id": device_id})


def get_es_mode(device_id: int = 0) -> str:
    """Get device operating mode and battery info command."""
    return build_command(CMD_ES_MODE, {"id": device_id})


def get_pv_status(device_id: int = 0) -> str:
    """Get device PV status command."""
    return build_command(CMD_PV_GET_STATUS, {"id": device_id})


def set_es_mode_manual_charge(device_id: int = 0, power: int = -1300) -> str:
    """Set manual charge mode command."""
    config = {
        "mode": "Manual",
        "manual_cfg": {
            "time_num": 0,
            "start_time": "00:00",
            "end_time": "23:59",
            "week_set": 127,  # Binary: all days enabled
            "power": power,  # Negative for charging
            "enable": 1,
        },
    }
    return build_command(CMD_ES_SET_MODE, {"id": device_id, "config": config})


def set_es_mode_manual_discharge(device_id: int = 0, power: int = 1300) -> str:
    """Set manual discharge mode command."""
    config = {
        "mode": "Manual",
        "manual_cfg": {
            "time_num": 0,
            "start_time": "00:00",
            "end_time": "23:59",
            "week_set": 127,  # Binary: all days enabled
            "power": power,  # Positive for discharging
            "enable": 1,
        },
    }
    return build_command(CMD_ES_SET_MODE, {"id": device_id, "config": config})
