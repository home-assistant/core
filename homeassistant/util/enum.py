"""Helpers for working with enums."""

from collections.abc import Callable
import contextlib
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

# https://github.com/python/mypy/issues/5107
if TYPE_CHECKING:
    _LruCacheT = TypeVar("_LruCacheT", bound=Callable)

    def lru_cache(func: _LruCacheT) -> _LruCacheT:
        """Stub for lru_cache."""

else:
    from functools import lru_cache

_EnumT = TypeVar("_EnumT", bound=Enum)


@lru_cache
def try_parse_enum(cls: type[_EnumT], value: Any) -> _EnumT | None:
    """Try to parse the value into an Enum.

    Return None if parsing fails.
    """
    with contextlib.suppress(ValueError):
        return cls(value)
    return None
