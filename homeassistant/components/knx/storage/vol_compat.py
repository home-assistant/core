"""Adapter to use voluptuous based validators in probatio schemas."""

from collections.abc import Callable
from typing import Any

import probatio as prb
import voluptuous as vol


def _convert(exc: vol.Invalid) -> prb.Invalid:
    """Convert a voluptuous error to its probatio counterpart."""
    if isinstance(exc, vol.MultipleInvalid):
        return prb.MultipleInvalid([_convert(error) for error in exc.errors])
    return prb.Invalid(exc.msg, path=list(exc.path))


class VolValidator:
    """Wrap a voluptuous based validator for use in a probatio schema.

    probatio only handles its own `Invalid` (and `ValueError`) raised from
    validator callables, so voluptuous errors need to be translated.
    """

    def __init__(self, validator: Callable[[Any], Any]) -> None:
        """Initialize the wrapper."""
        self.validator = validator

    def __call__(self, value: Any) -> Any:
        """Validate the value with the wrapped validator."""
        try:
            return self.validator(value)
        except vol.Invalid as exc:
            raise _convert(exc) from exc
