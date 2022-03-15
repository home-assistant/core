"""Diagnostic utilities."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar, cast, overload

from homeassistant.core import callback

from .const import REDACTED

T = TypeVar("T")


@overload
def async_redact_data(data: Mapping, to_redact: Iterable[Any]) -> dict:  # type: ignore[misc]
    ...


@overload
def async_redact_data(data: T, to_redact: Iterable[Any]) -> T:
    ...


@callback
def async_redact_data(data: T, to_redact: Iterable[Any]) -> T:
    """Redact sensitive data in a dict."""
    if not isinstance(data, (Mapping, list)):
        return data

    if isinstance(data, list):
        return cast(T, [async_redact_data(val, to_redact) for val in data])

    redacted = {**data}

    for key, value in redacted.items():
        if key in to_redact:
            redacted[key] = REDACTED
        elif isinstance(value, Mapping):
            redacted[key] = async_redact_data(value, to_redact)
        elif isinstance(value, list):
            redacted[key] = [async_redact_data(item, to_redact) for item in value]

    return cast(T, redacted)
