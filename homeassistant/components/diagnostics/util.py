"""Diagnostic utilities."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar, cast

from homeassistant.core import callback

from .const import REDACTED

T = TypeVar("T")


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
        elif isinstance(value, dict):
            redacted[key] = async_redact_data(value, to_redact)
        elif isinstance(value, list):
            redacted[key] = [async_redact_data(item, to_redact) for item in value]

    return cast(T, redacted)
