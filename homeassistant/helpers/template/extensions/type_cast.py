"""Type casting functions for Home Assistant templates."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import jinja2.filters

from homeassistant.helpers.template.helpers import forgiving_boolean, raise_no_default

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

_SENTINEL = object()


class TypeCastExtension(BaseTemplateExtension):
    """Jinja2 extension for type casting functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the type cast extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "bool",
                    forgiving_boolean,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "float",
                    self.forgiving_float,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "int",
                    self.forgiving_int,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "is_number",
                    self.is_number,
                    as_global=True,
                    as_filter=True,
                    as_test=True,
                ),
                TemplateFunction(
                    "string_like",
                    self.is_string_like,
                    as_test=True,
                ),
            ],
        )

    @staticmethod
    def forgiving_float(value: Any, default: Any = _SENTINEL) -> Any:
        """Try to convert value to a float."""
        try:
            return float(value)
        except ValueError, TypeError:
            if default is _SENTINEL:
                raise_no_default("float", value)
            return default

    @staticmethod
    def forgiving_int(value: Any, default: Any = _SENTINEL, base: int = 10) -> Any:
        """Try to convert value to an int, and raise if it fails."""
        result = jinja2.filters.do_int(value, default=default, base=base)
        if result is _SENTINEL:
            raise_no_default("int", value)
        return result

    @staticmethod
    def is_number(value: Any) -> bool:
        """Try to convert value to a float."""
        try:
            fvalue = float(value)
        except ValueError, TypeError:
            return False
        if not math.isfinite(fvalue):
            return False
        return True

    @staticmethod
    def is_string_like(value: Any) -> bool:
        """Return whether a value is a string or string like object."""
        return isinstance(value, (str, bytes, bytearray))
