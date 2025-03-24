"""Helpers for working with enums."""

from collections.abc import Callable
import contextlib
from enum import Enum
from typing import TYPE_CHECKING, Any

# https://github.com/python/mypy/issues/5107
if TYPE_CHECKING:

    def lru_cache[_T: Callable[..., Any]](func: _T) -> _T:
        """Stub for lru_cache."""

else:
    from functools import lru_cache


@lru_cache
def try_parse_enum[_EnumT: Enum](cls: type[_EnumT], value: Any) -> _EnumT | None:
    """Try to parse the value into an Enum.

    Return None if parsing fails.
    """
    with contextlib.suppress(ValueError):
        return cls(value)
    return None
