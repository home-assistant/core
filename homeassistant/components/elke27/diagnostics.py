"""Diagnostics support for Elke27."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Mapping

from elke27_lib import redact_for_diagnostics

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DOMAIN,
    MANUFACTURER_NUMBER,
)
from .hub import Elke27Hub


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub: Elke27Hub | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    snapshot = hub.snapshot if hub is not None else None
    snapshot_dict = _to_jsonable(snapshot)
    redacted_snapshot = redact_for_diagnostics(snapshot_dict)

    snapshot_meta = {
        "version": getattr(snapshot, "version", None),
        "updated_at": getattr(snapshot, "updated_at", None),
    }

    return {
        "entry_id": entry.entry_id,
        "host": entry.data.get(CONF_HOST),
        "port": entry.data.get(CONF_PORT),
        "manufacturer_number": MANUFACTURER_NUMBER,
        "integration_serial": entry.data.get(CONF_INTEGRATION_SERIAL),
        "link_keys_present": CONF_LINK_KEYS_JSON in entry.data,
        "snapshot_available": snapshot is not None,
        "snapshot_meta": snapshot_meta,
        "snapshot": redacted_snapshot,
    }


def _to_jsonable(value: Any) -> Any:
    """Normalize snapshots to JSON-safe types."""
    if value is None:
        return None
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(val) for key, val in value.items()}
    if isinstance(value, list | tuple | set):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, bytes | bytearray | memoryview):
        return f"<{len(value)} bytes>"
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
