"""Diagnostic utilities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast, overload

import attr

from homeassistant.core import callback
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


def _entity_entry_filter(a: attr.Attribute, _: Any) -> bool:
    return a.name != "_cache"


@callback
def entity_entry_as_dict(entry: RegistryEntry) -> dict[str, Any]:
    """Convert an entity registry entry to a dict for diagnostics.

    This excludes internal fields that should not be exposed in diagnostics.
    """
    return attr.asdict(entry, filter=_entity_entry_filter)
