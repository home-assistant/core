"""Diagnostics support for Teltonika integration."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import TeltonikaConfigEntry

REDACT_CONFIG = {"password"}


def _serialize_device_info(entry: TeltonikaConfigEntry) -> dict[str, Any]:
    # DeviceInfo is a TypedDict, convert to plain dict for serialization
    device_info_dict: dict[str, Any] = dict(entry.runtime_data.device_info)

    result: dict[str, Any] = {}
    for key, value in device_info_dict.items():
        if value is None:
            continue
        if key == "identifiers":
            # Convert set of tuples to list of lists for JSON serialization
            result[key] = sorted([list(identifier) for identifier in value])
        else:
            result[key] = _coerce(value)

    return result


def _serialize_modem(modem_id: str, modem: Any) -> dict[str, Any]:
    keys = (
        "name",
        "conntype",
        "operator",
        "state",
        "band",
        "rssi",
        "rsrp",
        "rsrq",
        "sinr",
        "temperature",
        "txbytes",
        "rxbytes",
    )

    data: dict[str, Any] = {"id": modem_id}
    for key in keys:
        value = getattr(modem, key, None)
        if value is None:
            continue
        data[key] = _coerce(value)
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Teltonika config entry."""

    teltonika_entry: TeltonikaConfigEntry = entry
    runtime_data = teltonika_entry.runtime_data
    coordinator = runtime_data.coordinator

    coordinator_data = coordinator.data or {}
    modems = [
        _serialize_modem(modem_id, modem)
        for modem_id, modem in coordinator_data.items()
    ]

    last_update_time = _coerce(getattr(coordinator, "last_update_success_time", None))

    return {
        "entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": last_update_time,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "modems": modems,
        },
        "device": _serialize_device_info(teltonika_entry),
    }


def _coerce(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _coerce(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_coerce(item) for item in value]
    if isinstance(value, tuple):
        return [_coerce(item) for item in value]
    if isinstance(value, set):
        return [_coerce(item) for item in sorted(value)]
    return str(value)
