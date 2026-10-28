"""Diagnostics support for iRobot Roomba."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import roomba_reported_state
from .models import RoombaConfigEntry

TO_OMIT = {
    "mac",
    "mobSerNo",
    "name",
    "navSerialNo",
    "netinfo",
    "wlan0HwAddr",
    "wlcfg",
}


def _omit_keys(data: Any) -> Any:
    """Recursively drop sensitive keys."""
    if isinstance(data, dict):
        return {k: _omit_keys(v) for k, v in data.items() if k not in TO_OMIT}
    if isinstance(data, list):
        return [_omit_keys(item) for item in data]
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RoombaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    roomba = entry.runtime_data.roomba
    return {
        "connected": roomba.connected,
        "current_state": roomba.current_state,
        "error_code": roomba.error_code,
        "error_message": roomba.error_message,
        "reported_state": _omit_keys(roomba_reported_state(roomba)),
    }
