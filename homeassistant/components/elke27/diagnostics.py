"""Diagnostics support for Elke27."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
import enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from elke27_lib import redact_for_diagnostics

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_INTEGRATION_SERIAL, CONF_LINK_KEYS_JSON, MANUFACTURER_NUMBER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .models import Elke27RuntimeData


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: Elke27RuntimeData | None = entry.runtime_data
    snapshot = data.coordinator.data if data is not None else None
    snapshot_dict = _to_jsonable(snapshot)
    redacted_snapshot = redact_for_diagnostics(snapshot_dict)

    snapshot_meta = _to_jsonable(
        {
            "version": getattr(snapshot, "version", None),
            "updated_at": getattr(snapshot, "updated_at", None),
        }
    )

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
        return {
            field.name: _to_jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, MappingProxyType):
        return {str(key): _to_jsonable(val) for key, val in dict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(val) for key, val in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted([_to_jsonable(item) for item in value], key=str)
    if isinstance(value, bytes | bytearray):
        return value.hex()
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
