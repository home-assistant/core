"""Helpers for working with enums."""
import contextlib
from enum import Enum
from typing import Any, TypeVar

_EnumT = TypeVar("_EnumT", bound=Enum)


def try_parse_enum(cls: type[_EnumT], value: Any) -> _EnumT | None:
    """Create a new StrEnum instance."""
    with contextlib.suppress(ValueError):
        return cls(value)
    return None
