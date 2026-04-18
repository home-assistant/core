"""Diagnostics support for OpenDisplay."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import OpenDisplayConfigEntry

TO_REDACT = {"ssid", "password", "server_url"}


def _asdict(obj: Any) -> Any:
    """Recursively convert a dataclass to a dict, encoding bytes as hex strings."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _asdict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, list):
        return [_asdict(item) for item in obj]
    return obj


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OpenDisplayConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    fw = runtime.firmware

    return {
        "firmware": {
            "major": fw["major"],
            "minor": fw["minor"],
            "sha": fw["sha"],
        },
        "is_flex": runtime.is_flex,
        "device_config": async_redact_data(_asdict(runtime.device_config), TO_REDACT),
    }
