"""Diagnostic utilities."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.core import callback

from .const import REDACTED


@callback
def async_redact_data(
    data: list | dict[str, Any], to_redact: Iterable[Any]
) -> list | dict[str, Any]:
    """Redact sensitive data in a dict."""
    if not isinstance(data, (Mapping, list)):
        return data

    if isinstance(data, list):
        return [async_redact_data(val, to_redact) for val in data]

    redacted = {**data}

    for key, value in redacted.items():
        if key in to_redact:
            redacted[key] = REDACTED
        elif isinstance(value, dict):
            redacted[key] = async_redact_data(value, to_redact)
        elif isinstance(value, list):
            redacted[key] = [async_redact_data(item, to_redact) for item in value]

    return redacted
