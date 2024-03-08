"""Helpers to redact sensitive data."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any, TypeVar, cast, overload

from homeassistant.core import callback

REDACTED = "**REDACTED**"

_T = TypeVar("_T")
_ValueT = TypeVar("_ValueT")


def partial_redact(
    x: str | Any, unmasked_prefix: int = 4, unmasked_suffix: int = 4
) -> str:
    """Mask part of a string with *."""
    if not isinstance(x, str):
        return REDACTED

    unmasked = unmasked_prefix + unmasked_suffix
    if len(x) < unmasked * 2:
        return REDACTED

    if not unmasked_prefix and not unmasked_suffix:
        return REDACTED

    suffix = x[-unmasked_suffix:] if unmasked_suffix else ""
    return f"{x[:unmasked_prefix]}***{suffix}"


@overload
def async_redact_data(  # type: ignore[overload-overlap]
    data: Mapping, to_redact: Iterable[Any] | Mapping[Any, Callable[[_ValueT], _ValueT]]
) -> dict:
    ...


@overload
def async_redact_data(
    data: _T, to_redact: Iterable[Any] | Mapping[Any, Callable[[_ValueT], _ValueT]]
) -> _T:
    ...


@callback
def async_redact_data(
    data: _T, to_redact: Iterable[Any] | Mapping[Any, Callable[[_ValueT], _ValueT]]
) -> _T:
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
            if isinstance(to_redact, Mapping):
                redacted[key] = to_redact[key](value)
            else:
                redacted[key] = REDACTED
        elif isinstance(value, Mapping):
            redacted[key] = async_redact_data(value, to_redact)
        elif isinstance(value, list):
            redacted[key] = [async_redact_data(item, to_redact) for item in value]

    return cast(_T, redacted)
