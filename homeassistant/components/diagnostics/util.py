"""Diagnostic utilities."""

from collections.abc import Iterable, Mapping
from typing import Any, cast, overload

import attr

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import REDACTED


@overload
def async_redact_data(data: Mapping, to_redact: Iterable[Any]) -> dict: ...


@overload
def async_redact_data[_T](data: _T, to_redact: Iterable[Any]) -> _T: ...


@callback
def async_redact_data[_T](data: _T, to_redact: Iterable[Any]) -> _T:
    """Redact sensitive data in a dict."""
    if not isinstance(data, (Mapping, list)):
        return data

    if isinstance(data, list):
        return cast(_T, [async_redact_data(val, to_redact) for val in data])

    redacted = {**data}

    for key, value in redacted.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        if key in to_redact:
            redacted[key] = REDACTED
        elif isinstance(value, Mapping):
            redacted[key] = async_redact_data(value, to_redact)
        elif isinstance(value, list):
            redacted[key] = [async_redact_data(item, to_redact) for item in value]

    return cast(_T, redacted)


# DeviceEntry attributes that are internal bookkeeping and must not be exposed in
# diagnostics. Underscore attributes (_cache, _suggested_area, and the transient
# _pending_move / _composite_subentries) are excluded separately by _device_entry_filter.
# The composite-device migration attributes below can be removed in HA Core 2027.8.
_INTERNAL_DEVICE_ENTRY_ATTRIBUTES = (
    "composite_device_id",
    "composite_primary_config_entry",
    "has_composite_identifiers",
    "split_at",
)


def _device_entry_filter(a: attr.Attribute, _: Any) -> bool:
    return (
        not a.name.startswith("_") and a.name not in _INTERNAL_DEVICE_ENTRY_ATTRIBUTES
    )


@callback
def device_entry_as_dict(entry: DeviceEntry) -> dict[str, Any]:
    """Convert a device registry entry to a dict for diagnostics.

    This excludes internal fields that should not be exposed in diagnostics.
    """
    return attr.asdict(entry, filter=_device_entry_filter)


def _entity_entry_filter(a: attr.Attribute, _: Any) -> bool:
    return a.name not in (
        "_cache",
        "compat_aliases",
        "original_name_unprefixed",
    )


@callback
def entity_entry_as_dict(entry: RegistryEntry) -> dict[str, Any]:
    """Convert an entity registry entry to a dict for diagnostics.

    This excludes internal fields that should not be exposed in diagnostics.
    """
    return attr.asdict(entry, filter=_entity_entry_filter)
