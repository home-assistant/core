"""Decorator utility functions."""
from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any, TypeVar

_KT = TypeVar("_KT", bound=Hashable)
_VT = TypeVar("_VT", bound=Callable[..., Any])


class Registry(dict[_KT, _VT]):
    """Registry of items."""

    def register(self, name: _KT) -> Callable[[_VT], _VT]:
        """Return decorator to register item with a specific name."""

        def decorator(func: _VT) -> _VT:
            """Register decorated function."""
            self[name] = func
            return func

        return decorator
