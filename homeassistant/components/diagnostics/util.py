"""Diagnostic utilities."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any, TypeVar

from homeassistant.core import callback

from .const import REDACTED

T = TypeVar("T")


@callback
def async_redact_data(data: T, to_redact: Iterable[Any]) -> T:
    """Redact sensitive data in a dict."""
    if not isinstance(data, (Mapping, list)):
        return data

    redacted = deepcopy(data)

    if isinstance(redacted, dict):
        for key, value in redacted.items():
            if key in to_redact:
                redacted[key] = REDACTED
            elif isinstance(value, dict):
                redacted[key] = async_redact_data(value, to_redact)
            elif isinstance(value, list):
                redacted[key] = [async_redact_data(item, to_redact) for item in value]
    elif isinstance(redacted, list):
        for idx, value in enumerate(redacted):
            redacted[idx] = async_redact_data(value, to_redact)

    return redacted
