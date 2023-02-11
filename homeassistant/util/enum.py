"""Helpers for working with enums."""
from collections.abc import Callable
import contextlib
from enum import Enum
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

# https://github.com/python/mypy/issues/5107
if TYPE_CHECKING:
    _P = ParamSpec("_P")
    _T = TypeVar("_T")

    def lru_cache(maxsize: int | None) -> Callable[..., Callable[_P, _T]]:
        """Stub for lru_cache."""

else:
    from functools import lru_cache

_EnumT = TypeVar("_EnumT", bound=Enum)


@lru_cache(1024)
def try_parse_enum(cls: type[_EnumT], value: Any) -> _EnumT | None:
    """Try to parse the value into an Enum.

    Return None if parsing fails.
    """
    with contextlib.suppress(ValueError):
        return cls(value)
    return None
