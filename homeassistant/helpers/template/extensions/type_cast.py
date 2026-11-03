"""Type casting functions for Home Assistant templates."""

import math
from typing import TYPE_CHECKING, Any

import jinja2.filters
from typing_extensions import Sentinel as sentinel

from homeassistant.helpers.template.helpers import forgiving_boolean, raise_no_default

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

_SENTINEL = sentinel("_SENTINEL")


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
    def forgiving_float[_T](
        value: Any, default: _T | _SENTINEL = _SENTINEL
    ) -> float | _T:
        """Try to convert value to a float."""
        try:
            return float(value)
        except ValueError, TypeError, OverflowError:
            if default is _SENTINEL:
                raise_no_default("float", value)
            return default

    @staticmethod
    def forgiving_int[_T](
        value: Any, default: _T | _SENTINEL = _SENTINEL, base: int = 10
    ) -> int | _T:
        """Try to convert value to an int, and raise if it fails."""
        result: int | _T | _SENTINEL
        try:
            # do_int annotates default as int but returns it unchanged
            result = jinja2.filters.do_int(value, default=default, base=base)  # type: ignore[arg-type]
        except OverflowError:
            # Jinja's do_int doesn't catch this for an infinite float
            result = default
        if result is _SENTINEL:
            raise_no_default("int", value)
        return result

    @staticmethod
    def is_number(value: Any) -> bool:
        """Try to convert value to a float."""
        try:
            fvalue = float(value)
        except ValueError, TypeError, OverflowError:
            return False
        if not math.isfinite(fvalue):
            return False
        return True

    @staticmethod
    def is_string_like(value: Any) -> bool:
        """Return whether a value is a string or string like object."""
        return isinstance(value, (str, bytes, bytearray))
